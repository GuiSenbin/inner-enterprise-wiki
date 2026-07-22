"""
定位：后端查询引擎层。
职责：扫描 Raw/Wiki 文档，构建索引与图谱，执行混合检索并生成带证据的回答。
依赖：本地知识库、FAISS、NetworkX 和 DashScope OpenAI 兼容接口。
"""

import os
import re
import pickle
import json
import faiss
import numpy as np
import networkx as nx
from dotenv import load_dotenv
from openai import OpenAI
import time

# 加载当前目录下的 .env 文件
load_dotenv()

class WikiEngine:
    """企业 Wiki 查询引擎，封装索引构建、混合检索和基于证据的回答生成。"""

    def __init__(self):
        """初始化项目路径、索引路径、模型客户端和运行时索引状态。"""
        # 自动定位当前项目根目录
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.raw_dir = os.path.join(self.project_dir, "Raw")
        self.concept_dir = os.path.join(self.project_dir, "Wiki/concept")
        self.entity_dir = os.path.join(self.project_dir, "Wiki/entity")
        
        self.index_save_dir = os.path.join(self.project_dir, "data/wiki_index")
        self.faiss_path = os.path.join(self.index_save_dir, "faiss.index")
        self.chunks_path = os.path.join(self.index_save_dir, "chunks.json")
        self.graph_path = os.path.join(self.index_save_dir, "graph.pkl")
        
        # 初始化 OpenAI 兼容客户端调用通义千问
        api_key = os.getenv("DASHSCOPE_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 运行时数据
        self.index = None
        self.chunks = []
        self.graph = None
        self.all_nodes = set()

    def get_embeddings(self, texts):
        """调用通义千问 text-embedding-v3 获取文本向量，失败时重试后抛出异常。"""
        batch_size = 25
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            retries = 3
            while retries > 0:
                try:
                    response = self.client.embeddings.create(
                        model="text-embedding-v3",
                        input=batch_texts
                    )
                    embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(embeddings)
                    break
                except Exception as e:
                    print(f"获取 Embedding 出错，重试中: {e}")
                    retries -= 1
                    time.sleep(2)
            if retries == 0:
                raise Exception("无法调用通义千问 Embedding API，重试失败。")
            time.sleep(0.2)
            
        return all_embeddings

    def split_markdown(self, text, chunk_size=2000, overlap=300):
        """按固定窗口切分 Markdown 文本，短文档保持单块，长文档使用重叠窗口。"""
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += chunk_size - overlap
        return chunks

    def build_index(self):
        """扫描 Raw 和 Wiki 文档，构建 FAISS 向量索引与 NetworkX 双链图谱并持久化。"""
        os.makedirs(self.index_save_dir, exist_ok=True)
        
        # 扫描并清理已有文件
        for f in [self.faiss_path, self.chunks_path, self.graph_path]:
            if os.path.exists(f):
                os.remove(f)

        print("开始扫描文档并提取数据...")
        
        raw_files = []
        concept_files = []
        entity_files = []
        
        if os.path.exists(self.raw_dir):
            raw_files = [f for f in os.listdir(self.raw_dir) if f.endswith(".md")]
        if os.path.exists(self.concept_dir):
            concept_files = [f for f in os.listdir(self.concept_dir) if f.endswith(".md")]
        if os.path.exists(self.entity_dir):
            entity_files = [f for f in os.listdir(self.entity_dir) if f.endswith(".md")]

        # 构建图谱拓扑
        graph = nx.Graph()
        
        concept_names = {os.path.splitext(f)[0] for f in concept_files}
        entity_names = {os.path.splitext(f)[0] for f in entity_files}
        wiki_names = concept_names | entity_names
        
        for name in wiki_names:
            graph.add_node(name, type="wiki_term")

        chunks = []
        texts_to_embed = []
        pattern = re.compile(r"\[\[(.*?)\]\]")

        for f_name in raw_files:
            doc_name = os.path.splitext(f_name)[0]
            file_path = os.path.join(self.raw_dir, f_name)
            
            graph.add_node(doc_name, type="raw_doc")
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            matches = pattern.findall(content)
            for m in matches:
                m_clean = m.strip()
                safe_kw = m_clean.replace("/", "_").replace("\\", "_")
                if safe_kw in wiki_names:
                    graph.add_edge(doc_name, safe_kw, relation="mentions")

            # 物理分块
            doc_chunks = self.split_markdown(content)
            for idx, chunk_text in enumerate(doc_chunks):
                chunk_meta = {
                    "id": len(chunks),
                    "doc_name": doc_name,
                    "file_name": f_name,
                    "category": "raw",
                    "text": chunk_text,
                    "mentions": [m.strip() for m in matches if m.strip()]
                }
                chunks.append(chunk_meta)
                texts_to_embed.append(chunk_text)

        # 把 Wiki/concept 和 Wiki/entity 词条分块写入向量数据库
        for f_name in concept_files:
            term_name = os.path.splitext(f_name)[0]
            file_path = os.path.join(self.concept_dir, f_name)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            doc_chunks = self.split_markdown(content)
            for idx, chunk_text in enumerate(doc_chunks):
                chunk_meta = {
                    "id": len(chunks),
                    "doc_name": term_name,
                    "file_name": f_name,
                    "category": "concept",
                    "text": chunk_text,
                    "mentions": []
                }
                chunks.append(chunk_meta)
                texts_to_embed.append(chunk_text)

        for f_name in entity_files:
            term_name = os.path.splitext(f_name)[0]
            file_path = os.path.join(self.entity_dir, f_name)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            doc_chunks = self.split_markdown(content)
            for idx, chunk_text in enumerate(doc_chunks):
                chunk_meta = {
                    "id": len(chunks),
                    "doc_name": term_name,
                    "file_name": f_name,
                    "category": "entity",
                    "text": chunk_text,
                    "mentions": []
                }
                chunks.append(chunk_meta)
                texts_to_embed.append(chunk_text)

        print(f"提取出 {len(chunks)} 个文本分块，开始获取向量...")
        embeddings = self.get_embeddings(texts_to_embed)
        
        # 写入 FAISS 索引
        dimension = 1024
        faiss_index = faiss.IndexFlatL2(dimension)
        embeddings_np = np.array(embeddings).astype("float32")
        faiss_index.add(embeddings_np)
        
        # 保存索引
        faiss.write_index(faiss_index, self.faiss_path)
        
        # 保存分块元数据
        with open(self.chunks_path, "w", encoding="utf-8") as out_f:
            json.dump(chunks, out_f, ensure_ascii=False, indent=2)
            
        # 保存图谱
        with open(self.graph_path, "wb") as out_g:
            pickle.dump(graph, out_g)
            
        print("所有本地索引保存完成！")
        
        self.index = faiss_index
        self.chunks = chunks
        self.graph = graph
        self.all_nodes = set(graph.nodes)

    def load_index(self):
        """载入本地持久化索引，缺失或损坏时返回 False。"""
        if not os.path.exists(self.faiss_path) or not os.path.exists(self.chunks_path) or not os.path.exists(self.graph_path):
            return False
            
        try:
            self.index = faiss.read_index(self.faiss_path)
            with open(self.chunks_path, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            with open(self.graph_path, "rb") as f:
                self.graph = pickle.load(f)
            self.all_nodes = set(self.graph.nodes)
            return True
        except Exception as e:
            print(f"载入索引失败: {e}")
            return False

    def extract_terms_from_query(self, query):
        """从用户问题中匹配已存在的 Wiki 图谱节点。"""
        matched_terms = []
        for node in self.all_nodes:
            norm_node = node.lower().replace("_", "/")
            norm_query = query.lower()
            if norm_node in norm_query or node.lower() in norm_query:
                matched_terms.append(node)
        return matched_terms

    def extract_date_from_doc_name(self, doc_name):
        """从文档名称中提取 YYYYMMDD 日期，无法提取时返回默认低值。"""
        match = re.search(r"(\d{8})", doc_name)
        if match:
            return match.group(1)
        return "00000000"

    def retrieve(self, query, top_k=5):
        """执行 FAISS 语义召回和图谱关联召回，返回重排后的证据切片。"""
        if self.index is None or not self.chunks:
            raise Exception("尚未载入或构建索引！")

        # 1. 尝试向量检索 (FAISS)
        vector_results = []
        embedding_failed = False
        try:
            query_emb = self.get_embeddings([query])[0]
            query_emb_np = np.array([query_emb]).astype("float32")
            vector_top_k = 15
            distances, indices = self.index.search(query_emb_np, vector_top_k)
            
            for i, idx in enumerate(indices[0]):
                if idx == -1:
                    continue
                dist = float(distances[0][i])
                chunk = self.chunks[idx]
                sim_score = 1.0 / (1.0 + dist)
                vector_results.append((chunk, sim_score))
        except Exception as e:
            print(f"Embedding 向量检索失败，将降级为纯本地图谱检索: {e}")
            embedding_failed = True

        # 2. 图关系检索
        matched_nodes = self.extract_terms_from_query(query)
        graph_related_docs = set()
        
        for node in matched_nodes:
            if node in self.graph:
                neighbors = self.graph.neighbors(node)
                for n in neighbors:
                    node_attrs = self.graph.nodes[n]
                    if node_attrs.get("type") == "raw_doc":
                        graph_related_docs.add(n)

        # 3. 混合重排 (Hybrid Rerank)
        scored_chunks = []
        seen_chunk_ids = set()

        if not embedding_failed:
            for chunk, v_score in vector_results:
                seen_chunk_ids.add(chunk["id"])
                score = v_score
                is_graph_hit = False
                
                if chunk["doc_name"] in graph_related_docs:
                    score += 0.35
                    is_graph_hit = True
                    
                date_str = self.extract_date_from_doc_name(chunk["doc_name"])
                try:
                    year = int(date_str[:4])
                    if year > 2020:
                        score += (year - 2020) * 0.005
                except:
                    pass
                    
                scored_chunks.append({
                    "chunk": chunk,
                    "score": score,
                    "vector_score": v_score,
                    "graph_hit": is_graph_hit
                })

        # 补充图关联的分块
        for chunk in self.chunks:
            if chunk["id"] not in seen_chunk_ids:
                if chunk["doc_name"] in graph_related_docs:
                    v_score = 0.30
                    score = v_score + 0.35 if not embedding_failed else 1.0
                    date_str = self.extract_date_from_doc_name(chunk["doc_name"])
                    try:
                        year = int(date_str[:4])
                        if year > 2020:
                            score += (year - 2020) * 0.005
                    except:
                        pass
                        
                    scored_chunks.append({
                        "chunk": chunk,
                        "score": score,
                        "vector_score": v_score,
                        "graph_hit": True
                    })
                    seen_chunk_ids.add(chunk["id"])

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        final_top_chunks = scored_chunks[:top_k]

        return final_top_chunks, matched_nodes, list(graph_related_docs), embedding_failed

    def answer_question(self, query, top_k=5, model="qwen-plus"):
        """基于检索证据组装 Prompt 并调用 LLM，返回答案、来源和降级状态。"""
        # 1. 混合检索
        retrieved_results, matched_nodes, related_docs, embedding_failed = self.retrieve(query, top_k=top_k)
        
        # 2. 组装上下文
        contexts = []
        for i, res in enumerate(retrieved_results):
            chunk = res["chunk"]
            meta_info = f"【信息源 {i+1}】文档：{chunk['doc_name']} | 类别：{chunk['category']}"
            contexts.append(f"{meta_info}\n内容：{chunk['text']}")
            
        context_str = "\n\n".join(contexts)

        # 3. 构造 Prompt
        prompt = f"""你是一个专业的企业内部知识库问答助手。请严格基于以下给出的【已知参考信息】回答用户的提问。如果参考信息中没有提到，请诚实回答不知道，严禁编造和捏造事实。

【已知参考信息】：
{context_str}

【用户提问】：
{query}

请给出严谨且结构清晰的中文回答："""

        # 4. 调用通义千问大模型进行生成，设计模型自动回退容灾机制
        fallback_models = [model, "qwen-plus-2025-07-28", "qwen-turbo", "qwen-long", "qwen-max"]
        models_to_try = []
        for m in fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

        last_exception = None
        completion = None
        used_model = None
        llm_failed = False

        for m in models_to_try:
            try:
                completion = self.client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": "你是一个严谨的企业Wiki问答助手，所有回答必须基于参考信息，禁止使用外部知识与幻觉。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                used_model = m
                break
            except Exception as e:
                print(f"使用模型 {m} 失败，自动尝试回退下一个: {e}")
                last_exception = e

        if completion is None:
            answer = f"由于您的 API 账户状态欠费或发生其他错误，大模型无法生成最终回答。原因为：{last_exception}"
            llm_failed = True
        else:
            answer = completion.choices[0].message.content

        return {
            "query": query,
            "answer": answer,
            "prompt": prompt,
            "matched_nodes": matched_nodes,
            "related_docs": related_docs,
            "retrieved_results": [
                {
                    "chunk": res["chunk"],
                    "score": res["score"],
                    "vector_score": res["vector_score"],
                    "graph_hit": res["graph_hit"]
                } for res in retrieved_results
            ],
            "used_model": used_model,
            "embedding_failed": embedding_failed,
            "llm_failed": llm_failed
        }
