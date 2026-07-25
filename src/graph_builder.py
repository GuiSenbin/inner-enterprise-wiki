"""
定位：知识编译图谱层。
职责：根据 Wiki 节点和 Raw 文档双链构建本地 LinkGraph。
依赖：NetworkX 和知识加载层输出。
"""

import networkx as nx

from src.models import LinkGraph


class GraphBuilder:
    """把实体、概念和 Raw 文档关系编译成双链图谱。"""

    def build(self, wiki_nodes, raw_mentions_by_doc):
        """创建 Raw 文档到 Wiki 节点的 mentions 边。"""
        concept_names = {node.name for node in wiki_nodes if node.node_type == "concept"}
        entity_names = {node.name for node in wiki_nodes if node.node_type == "entity"}
        wiki_names = concept_names | entity_names

        graph = nx.Graph()
        for node in wiki_nodes:
            graph.add_node(node.name, type=node.node_type)

        for doc_name, mentions in raw_mentions_by_doc.items():
            graph.add_node(doc_name, type="raw_doc")
            for mention in mentions:
                safe_kw = mention.replace("/", "_").replace("\\", "_")
                if safe_kw in wiki_names:
                    graph.add_edge(doc_name, safe_kw, relation="mentions")

        return LinkGraph(graph=graph, concept_names=concept_names, entity_names=entity_names)
