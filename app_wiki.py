import streamlit as st
import os
import sys
from pathlib import Path

# 将 src 目录加入 Python 搜索路径
sys.path.append(str(Path(__file__).parent))

from src.wiki_engine import WikiEngine

# 设置页面配置
st.set_page_config(page_title="AI 企业 Wiki 智能问答系统", layout="wide")

# 高级感 CSS 样式注入
st.markdown("""
<style>
    /* 引入高端 Google 字体 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* 全局页面字体与背景微调 */
    .stApp {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    
    /* 极简头部 Banner */
    .main-banner {
        background-color: #ffffff;
        padding: 30px 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 25px;
        border: 1px solid #e2e8f0;
    }
    
    .main-banner h1 {
        color: #1e3a8a;
        font-family: 'Inter', sans-serif !important;
        font-size: 32px;
        font-weight: 700;
        margin: 0;
    }
    
    .main-banner p {
        color: #64748b;
        margin: 6px 0 0 0;
        font-size: 14.5px;
    }
    
    /* 最终回答面板 - 简洁白底蓝边 */
    .answer-box {
        background-color: #ffffff;
        border-left: 5px solid #2563eb;
        padding: 20px;
        border-radius: 8px;
        font-size: 15px;
        line-height: 1.7;
        color: #1e293b;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* 图谱关联面板 - 简洁浅绿底 */
    .graph-info-box {
        background-color: #f0fdf4;
        border: 1px solid #dcfce7;
        border-left: 5px solid #16a34a;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 20px;
        font-size: 14.5px;
        color: #14532d;
    }
    
    /* 检索切片卡片 - 极简白底框（Padding 为 16px） */
    .chunk-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 15px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    }
    
    /* 区分类型的左侧彩色条 */
    .chunk-card.raw-card {
        border-left: 4px solid #3b82f6;
    }
    .chunk-card.concept-card {
        border-left: 4px solid #eab308;
    }
    .chunk-card.entity-card {
        border-left: 4px solid #22c55e;
    }
    
    .chunk-header {
        font-weight: 600;
        color: #334155;
        margin-bottom: 10px;
        font-size: 13.5px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* 精致小巧 Badge */
    .chunk-badge {
        font-size: 11px;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 4px;
    }
    .badge-raw {
        background-color: #eff6ff;
        color: #1e40af;
        border: 1px solid #bfdbfe;
    }
    .badge-concept {
        background-color: #fefdf0;
        color: #92400e;
        border: 1px solid #fef08a;
    }
    .badge-entity {
        background-color: #f0fdf4;
        color: #16532d;
        border: 1px solid #bbf7d0;
    }
    
    /* 核心代码字体正文框 - 限制最大高度为 180px 并使用滚动条防止过高 */
    .chunk-text-content {
        background-color: #f8fafc;
        padding: 12px 16px;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        font-size: 13.5px;
        line-height: 1.6;
        white-space: pre-wrap;
        color: #334155;
        margin-bottom: 10px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        max-height: 180px;
        overflow-y: auto;
    }
    
    /* 滚动条极简灰色样式 */
    .chunk-text-content::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    .chunk-text-content::-webkit-scrollbar-track {
        background: #f8fafc;
    }
    .chunk-text-content::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }
    .chunk-text-content::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
    
    .chunk-footer {
        font-size: 12px;
        color: #64748b;
        display: flex;
        justify-content: space-between;
    }
</style>
""", unsafe_allow_html=True)

# 初始化引擎
@st.cache_resource
def get_engine():
    engine = WikiEngine()
    engine.load_index()
    return engine

engine = get_engine()

# 渲染精美横幅
st.markdown("""
<div class="main-banner">
    <h1>AI 企业 Wiki 智能问答系统</h1>
    <p>混合检索技术支撑 | FAISS 本地向量检索 + NetworkX 语义关联图谱 | 通义千问大模型</p>
</div>
""", unsafe_allow_html=True)

# 侧边栏布局与状态显示
with st.sidebar:
    st.header("系统状态与建库")
    
    index_loaded = (engine.index is not None and len(engine.chunks) > 0)
    if index_loaded:
        st.success("本地索引：加载成功")
        st.metric("索引文本切片数 (Chunks)", len(engine.chunks))
        st.metric("知识图谱关联节点数", len(engine.all_nodes))
    else:
        st.warning("本地索引：未检测到，请先构建索引")

    st.markdown("---")
    
    st.subheader("大模型参数配置")
    llm_model = st.selectbox(
        "选择大语言模型 (LLM Model)",
        options=["qwen-plus-2025-07-28", "qwen-plus", "qwen-turbo", "qwen-max", "qwen-long"],
        index=0,
        help="如遇 403 免费额度耗尽错误，可切换至其它模型，或在百炼后台绑定支付方式并关闭仅限免费额度限制。"
    )

    st.markdown("---")
    
    st.subheader("知识库建库管理")
    rebuild_btn = st.button("一键构建 / 更新本地索引", use_container_width=True)
    if rebuild_btn:
        with st.spinner("正在扫描 Wiki 并请求千问 Embedding 接口构建索引，这可能需要 1-2 分钟..."):
            try:
                engine.build_index()
                st.success("索引构建成功！已在本地持久化。")
                st.rerun()
            except Exception as e:
                st.error(f"索引构建失败: {e}")

    st.markdown("---")
    st.markdown("数据读取源目录：")
    st.code(engine.project_dir)

# 主面板问答检索区
st.subheader("问答与检索")

# 推荐测试问题
st.markdown("推荐测试问题：")
col1, col2, col3 = st.columns(3)
with col1:
    q1 = st.button("星辰数智给中国移动做过什么项目？", use_container_width=True)
with col2:
    q2 = st.button("物联网管理平台的客户验收标准和来往账目结算条件是什么？", use_container_width=True)
with col3:
    q3 = st.button("介绍一下技术组件 Kubernetes 的选用理由。", use_container_width=True)

query = ""
if q1:
    query = "星辰数智给中国移动做过什么项目？"
elif q2:
    query = "物联网管理平台的客户验收标准和来往账目结算条件是什么？"
elif q3:
    query = "介绍一下技术组件 Kubernetes 的选用理由。"

st.markdown("请输入您的问题进行提问：")
input_col, btn_col = st.columns([5, 1.2])
with input_col:
    user_input = st.text_input(
        "query_input_text",
        value=query,
        placeholder="例如：微服务架构的设计原则是什么？",
        label_visibility="collapsed"
    )
with btn_col:
    search_btn = st.button("开始检索与回答", type="primary", use_container_width=True)

if (search_btn or user_input) and user_input.strip():
    query_text = user_input.strip()
    
    if not index_loaded:
        st.error("请先在左侧工具栏一键构建本地索引，再进行检索问答！")
    else:
        with st.spinner("正在执行图谱与向量混合检索，并调用通义千问生成回答..."):
            try:
                # 执行问答
                res = engine.answer_question(query_text, top_k=5, model=llm_model)
                # 异常警示展示
                if res.get("embedding_failed"):
                    st.warning("系统提示：由于您的通义千问 API 账户已欠费 (Arrearage)，本地向量化 Embedding 服务已被封禁。系统已自动为您降级为【纯本地知识图谱关联检索】。")
                
                if res.get("llm_failed"):
                    st.error("系统提示：由于您的 API 账户处于欠费状态，通义千问大语言模型生成功能已被拒绝服务。但下方依然为您提供了检索到的切片和发送提示词 (Prompt)，供您参考。")

                # 1. 最终回答
                st.markdown("### 最终回答 (LLM Answer)")
                used_model = res.get("used_model", llm_model)
                if not res.get("llm_failed"):
                    if used_model != llm_model:
                        st.warning(f"系统提示：由于您选择的 {llm_model} 免费额度耗尽 (403)，系统已自动启用备用模型 {used_model} 进行回答。")
                    else:
                        st.caption(f"当前使用生成模型：{used_model}")
                st.markdown(f'<div class="answer-box">{res["answer"]}</div>', unsafe_allow_html=True)
                
                 # 2. 图谱关系匹配
                st.markdown("### 图谱关系匹配 (Graph Association)")
                matched_nodes_str = ", ".join(res["matched_nodes"]) if res["matched_nodes"] else "无"
                related_docs_str = ", ".join(res["related_docs"]) if res["related_docs"] else "无"
                
                st.markdown(f"""
                <div class="graph-info-box">
                    <strong>提取到的关键词 (Matched Keywords)：</strong> <code style="color:#0f766e; font-weight:600;">{matched_nodes_str}</code><br/>
                    <div style="margin-top:6px;"></div>
                    <strong>图谱关联到的原始文档 (一度链接)：</strong> <code style="color:#1d4ed8; font-weight:600;">{related_docs_str}</code>
                </div>
                """, unsafe_allow_html=True)

                # 3. 最终组装的提示词
                st.markdown("### 组装提示词全貌 (Context Prompt)")
                with st.expander("显示发送给通义千问大模型的完整 Prompt 内容"):
                    st.code(res["prompt"], language="markdown")

                # 4. 检索到的切片正文展示（含 hover 和彩色边框）
                st.markdown(f"### 检索到的原始切片正文 (共 {len(res['retrieved_results'])} 个)")
                for idx, item in enumerate(res["retrieved_results"]):
                    chunk = item["chunk"]
                    score = item["score"]
                    vector_score = item["vector_score"]
                    graph_hit = item["graph_hit"]

                    # 检索依据与样式判定
                    if graph_hit and vector_score > 0.30:
                        source_label = "双侧检索 (向量匹配且存在图谱关联)"
                        source_style = "color:#6366f1; font-weight:600;"
                    elif not graph_hit:
                        source_label = "语义检索 (仅由向量库相似召回)"
                        source_style = "color:#2563eb; font-weight:600;"
                    else:
                        source_label = "关键词检索 (本地图拓扑反链强行召回)"
                        source_style = "color:#16a34a; font-weight:600;"

                    # 确定分类边框类与徽章类型
                    if chunk["category"] == "raw":
                        card_class = "raw-card"
                        badge_class = "badge-raw"
                        cat_label = "原始文档"
                    elif chunk["category"] == "concept":
                        card_class = "concept-card"
                        badge_class = "badge-concept"
                        cat_label = "概念词条"
                    else:
                        card_class = "entity-card"
                        badge_class = "badge-entity"
                        cat_label = "实体词条"
                    
                    st.markdown(f"""
                    <div class="chunk-card {card_class}">
                        <div class="chunk-header">
                            <span>切片 #{idx + 1} | 来源文档：{chunk['doc_name']}</span>
                            <span class="chunk-badge {badge_class}">{cat_label}</span>
                        </div>
                        <div class="chunk-text-content">{chunk['text']}</div>
                        <div class="chunk-footer" style="flex-direction: column; gap: 4px;">
                            <div style="display: flex; justify-content: space-between; width: 100%;">
                                <span><strong>检索依据</strong>：<span style="{source_style}">{source_label}</span></span>
                                <span><strong>相似度评分</strong>：语义分 <code style="color:#2563eb; font-weight:600;">{vector_score:.3f}</code> | 综合权重分 <code style="color:#4f46e5; font-weight:600;">{score:.3f}</code></span>
                            </div>
                            <div style="font-size: 11.5px; color: #64748b; margin-top: 4px; border-top: 1px dashed #e2e8f0; padding-top: 4px;">
                                <strong>提及的双链链接：</strong> {", ".join(chunk['mentions']) if chunk['mentions'] else '无'}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"处理问答请求时发生错误: {e}")
                import traceback
                st.code(traceback.format_exc())
else:
    if not index_loaded:
        st.info("检测到您尚未构建索引。请在左侧工具栏点击【一键构建 / 更新本地索引】按钮以开始。")
    else:
        st.info("请在上方输入框内键入提问，或点击推荐测试问题快速开始。")
