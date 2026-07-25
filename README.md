# 合晟资产知识编译型 LLM Wiki

这是一个面向企业内部项目文档的**知识编译型 LLM Wiki**。项目以合晟资产内部数字化项目资料为样本，把 `Raw/` 原始文档、`Wiki/concept/` 概念词条、`Wiki/entity/` 实体词条和 Markdown 双链关系提前编译成稳定知识中间件，再通过意图识别、混合检索、轻量重排和大模型生成，回答复杂、跨文档、可追溯的问题。

RAG 是底层召回能力，不是产品核心。传统 RAG 更像“用户提问时临时查原文、现场拼上下文”；本项目更强调先把企业知识整理、切块、关联、索引和评估，形成可复用的 `DocumentChunk`、`WikiNode`、`LinkGraph`、`RetrievalCandidate` 和 `AnswerEvidence`，再让问答链路消费这些已编译 Wiki 证据。

```text
Raw/Wiki 文档
  -> 知识编译中间件
  -> 意图识别
  -> 向量召回 + BM25 关键词召回 + 双链图谱召回
  -> 可解释轻量重排
  -> 证据置信度判断
  -> 基于证据的中文回答
  -> 页面展示答案、来源、Prompt、策略和重排依据
```

## 当前版本 3.0

V3.0 完成第一阶段产品内核重塑：在保留现有 Raw、概念、实体和双链图谱资产的前提下，把早期集中在 `WikiEngine` 中的扫描、切片、索引、图谱、召回、重排、Prompt 和模型调用拆成清晰层级，使系统从“一个可运行的 RAG Demo”升级为“可解释、可验证、可继续扩展的企业 LLM Wiki”。

1. 系统内置 **12 个内部数字化项目**，每个项目固定包含需求规格、技术方案、项目管理计划、系统测试报告和内部验收报告，总计 60 份 Raw 文档。
2. `Wiki/concept/` 和 `Wiki/entity/` 继续作为核心知识资产，Raw 文档通过 `[[双链]]` 关联项目、部门、人员、技术组件和业务概念。
3. 知识编译阶段优先使用 LangChain Markdown splitter，依赖不可用时回退到固定 2000 字窗口和 300 字重叠切片。
4. 检索索引同时包含 DashScope `qwen3.7-text-embedding` + FAISS 向量索引、本地 BM25 关键词索引和 NetworkX 双链图谱。
5. 查询阶段新增轻量意图识别，区分原文定位、实体画像、概念归纳、项目事实、对比综合和普通问答。
6. 重排阶段综合语义分、BM25 关键词分、图谱命中、双链命中、文档类型、日期权重和直接事实命中，并返回排序原因。
7. 回答阶段根据证据状态和置信度判断是否调用大模型；证据不足、领域外或低置信问题会直接兜底，减少幻觉和无效调用。
8. API 返回 `intent_type`、`retrieval_strategy`、`rerank_explanation`、`evidence_status`、`confidence_score`、`confidence_label` 和 Top 5 证据切片。
9. 页面展示索引状态、切片数、图谱节点、双链关系、编译时间、问题意图、检索策略、重排依据、证据置信度、最终回答和证据轨道。
10. 测试覆盖知识库一致性、知识编译规则、意图识别、BM25 召回、轻量重排、证据兜底、模型配置、HTTP API 契约和前端展示边界。

💗 亮点：V3.0 的重点不是继续堆页面功能，而是回答企业知识库最核心的问题：**文档多了如何治理，问题来了如何找准，证据不足如何拒答，答案生成后如何解释来源，后续如何持续评估和优化。**

——————————————————————————————————————————————————

## 核心能力

### 1. 知识编译层

系统不是在用户提问时临时处理文档，而是在索引构建阶段把 Raw/Wiki 文档编译成稳定知识单元：

- `DocumentChunk`：保存正文、来源文档、文档类型、分类、双链 mentions 和源路径。
- `WikiNode`：表示来自 `Wiki/concept/` 或 `Wiki/entity/` 的知识节点。
- `LinkGraph`：保存 Raw 文档与实体/概念之间的双链关系。
- `RetrievalCandidate`：统一承载向量召回、BM25 关键词召回和图谱召回的候选证据。
- `AnswerEvidence`：最终进入 Prompt 和前端证据轨道的证据单元。

这层的价值是把“文件”转成“可检索、可解释、可复用的知识资产”，后续无论换前端、换模型还是换检索策略，都不需要推翻知识库结构。

### 2. 查询意图识别

`query_router` 使用轻量规则识别问题类型，不额外调用大模型：

| 意图 | 典型问题 | 检索策略 |
| --- | --- | --- |
| 原文定位 | “某条款原文是什么？” | 向量优先，保留原文切片 |
| 实体画像 | “李娜参与过哪些项目？” | 实体 / 双链图谱优先 |
| 概念归纳 | “哪些项目涉及监管留痕？” | 概念节点 + 图谱扩展 |
| 项目事实 | “投研数据中台的验收指标有哪些？” | 混合召回 + 文档类型加权 |
| 对比综合 | “对比两个系统的权限设计差异” | 多节点混合召回 |
| 普通问答 | 默认企业 Wiki 问题 | 向量 + BM25 + 图谱补充 |

这一步让系统先判断“该怎么找资料”，而不是所有问题都走同一个 Top K 向量召回。

### 3. 混合检索

检索阶段同时使用三类信号：

- **FAISS 向量召回**：解决语义相似、表达不完全一致的问题。
- **BM25 关键词召回**：补足编号、字段、指标、百分比和专有名词等精确匹配场景。
- **Wiki 双链图谱召回**：沿实体/概念节点找到关联 Raw 文档，支持跨项目和多跳问题。

如果 Embedding 服务不可用，系统会保留 BM25 和图谱召回结果，并在 API 与页面中标记 `embedding_failed`。

### 4. 可解释轻量重排

当前版本没有引入额外模型 rerank，而是使用可解释规则增强排序：

- 问验收时优先 `内部验收报告`。
- 问需求范围时优先 `需求规格说明书`。
- 问架构/技术时优先 `技术方案`。
- 问计划、负责人、周期时优先 `项目管理计划`。
- 问测试和缺陷时优先 `系统测试报告`。
- 命中编号、数字、百分比或完整事实短语时提高直接事实分。
- 命中实体、概念或 Raw 双链时增加图谱和双链权重。

每个 Top 证据都会返回 `rerank_reasons`，前端能展示“为什么这条证据排在前面”。

### 5. 有证据回答与拒答

`AnswerService` 负责把 Top 证据组装为“已编译 Wiki 证据”，再调用通义千问 OpenAI 兼容接口生成中文回答。Prompt 明确要求：

- 严格基于证据回答。
- 证据没有提到时说明不知道。
- 禁止使用外部知识和编造事实。

在进入大模型前，系统会先判断证据状态：

- `out_of_scope`：问题不属于当前合晟资产内部 Wiki 范围。
- `no_evidence`：问题属于范围内，但没有找到可用证据。
- `low_confidence`：存在候选证据，但信号太弱，不足以支撑回答。
- `ok`：证据足够，进入 Prompt 生成。

页面中的“证据置信度”来自检索证据质量评分，不是大模型自评。

——————————————————————————————————————————————————

## 版本演进

### V1：Streamlit Wiki 原型

目标是先验证企业项目文档能否整理成可查询 Wiki。该阶段使用 Streamlit 快速搭建页面，能输入问题并查看回答，但文档量偏多、页面展示偏弱，检索过程和回答质量不容易人工核对。

### V2：可验证 RAG 闭环

目标是把原型收敛为可演示、可核对的 RAG 主链路。该阶段缩减并规范文档集为 12 个项目、5 类文档、60 份 Raw 资料，补充 Raw/Wiki 双链、FAISS 向量索引、图谱增强、Prompt 展示、Top 5 证据轨道和原生 Web 页面。

### V3：知识编译型 LLM Wiki

目标是回答更深入的工程问题：文档太多怎么办、如何越找越准、复杂问题如何路由、证据不足如何拒答、检索质量如何评估。该阶段拆分知识编译、意图路由、混合检索、轻量重排和有证据回答模块，并把策略、置信度和重排原因暴露给 API 与页面。

### 后续方向

1. 增量编译：只更新变化文档对应的切片、索引和图谱。
2. 元数据过滤：按项目、部门、文档类型、日期、密级做检索范围约束。
3. 语义切块：从固定窗口进一步升级为按标题、表格、章节和语义边界切块。
4. Query rewrite：对复杂问题做问题改写、拆解和多跳检索。
5. 模型 rerank：在轻量规则后增加 Cross-Encoder 或 LLM rerank，对难问题做二次排序。
6. 引用校验：让每个关键结论绑定具体证据切片和来源文档。
7. 检索评估集：建立固定问题、期望来源、Top K 命中率、引用准确率和人工评分。
8. 企业安全：增加权限过滤、脱敏、访问审计、部门隔离和密级标记。

——————————————————————————————————————————————————

## 技术架构

- 后端服务：Python 标准库 `ThreadingHTTPServer`
- 前端页面：原生 HTML、CSS、JavaScript
- 知识编译：Markdown Raw 文档 + Wiki 概念词条 + Wiki 实体词条 + 双链解析
- 切块策略：LangChain Markdown splitter 优先，固定 2000/300 窗口兜底
- 向量索引：FAISS
- 关键词索引：纯 Python BM25
- 图谱关系：NetworkX
- Embedding：在 `src/config.py` 统一配置，默认 DashScope `qwen3.7-text-embedding`
- 大模型：在 `src/config.py` 统一配置，默认 `qwen-plus-2025-07-28`
- 配置管理：`.env` + `src/config.py`
- 测试框架：unittest

## 目录结构

| 路径 | 作用 |
| --- | --- |
| `server.py` | HTTP 服务入口，提供静态页面、状态接口、问答接口和知识编译入口 |
| `src/wiki_engine.py` | LLM Wiki 门面类，协调知识编译、检索、重排和回答 |
| `src/models.py` | 编译、检索、重排和回答共享的数据结构 |
| `src/knowledge_loader.py` | 扫描 Raw/Wiki，解析双链、文档类型和源路径 |
| `src/chunker.py` | Markdown 切块，支持 LangChain splitter 和固定窗口兜底 |
| `src/graph_builder.py` | 构建 Wiki 双链图谱 |
| `src/vector_store.py` | Embedding、FAISS 构建、保存、加载和语义搜索 |
| `src/bm25_store.py` | 纯 Python BM25 关键词索引和本地关键词搜索 |
| `src/query_router.py` | 轻量意图识别和检索策略选择 |
| `src/retriever.py` | 向量召回、BM25 关键词召回、图谱召回和候选合并 |
| `src/reranker.py` | 可解释轻量重排 |
| `src/answer_service.py` | Prompt 组装、模型调用、证据状态和置信度估算 |
| `Raw/` | 60 份合晟资产内部项目 Markdown 原始文档 |
| `Wiki/concept/` | 概念词条库 |
| `Wiki/entity/` | 实体词条库 |
| `data/wiki_index/` | 本地知识编译产物和索引文件 |
| `web/` | 原生前端页面，负责输入、状态、答案和证据展示 |
| `tests/` | 知识库一致性、知识编译、模型配置、服务 API 和前端契约测试 |
| `docs/constitution.md` | 项目工程规范和变更约束 |

## 模型配置

模型、fallback 顺序、Embedding 模型、Embedding 维度、批大小、Top K 和请求大小限制都集中在 `src/config.py`。如果要切换模型，优先修改：

- `DEFAULT_LLM_MODEL`
- `ALLOWED_LLM_MODELS`
- `LLM_FALLBACK_MODELS`
- `DEFAULT_EMBEDDING_MODEL`
- `EMBEDDING_DIMENSION`
- `EMBEDDING_BATCH_SIZE`
- `DEFAULT_TOP_K`
- `MAX_JSON_BODY_BYTES`

业务模块不应该散落硬编码模型名；`server.py`、`DashScopeEmbeddingClient`、`FaissVectorStore` 和 `AnswerService` 都从配置读取模型相关常量。

## 本地启动

### 1. 准备环境

建议使用 Python 3.11+，并准备 DashScope API Key。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 Key

在项目根目录创建 `.env`：

```bash
DASHSCOPE_API_KEY=你的 DashScope API Key
```

`.env` 不应该提交到仓库。

### 4. 启动服务

```bash
python server.py
```

访问：

```text
http://127.0.0.1:8000
```

如果 `data/wiki_index/` 为空，请在页面左侧点击“重新编译知识”。该操作会调用 Embedding 接口并生成本地 FAISS 索引。

## 推荐演示问题

```text
哪些系统要求操作留痕率达到 100%？
刘洋 都负责哪些项目？
哪些项目提到了主要风险？
投研数据中台的验收指标有哪些？
对比客户适当性管理系统和合规审查工作台在权限上的设计差异。
知识库智能问答系统为什么适合使用 RAG？
```

## 常用验证

```bash
# 运行全部测试
python -m unittest discover tests

# 验证知识库范围、双链和内容质量
python -m unittest tests.test_hesheng_kb_integrity -v

# 验证知识编译、意图识别、BM25、重排和证据兜底
python -m unittest tests.test_knowledge_compilation -v

# 验证服务 API 和前端契约
python -m unittest tests.test_server_api tests.test_frontend_contract -v

# 检查核心 Python 文件语法
python -m py_compile server.py src/*.py scripts/regenerate_hesheng_kb.py
```

## 开发约定

- Raw 文档是事实源，新增回答依据必须能追溯到 Raw 或 Wiki 词条。
- Wiki 实体和概念是核心知识资产，不应被降级为普通检索附件。
- 新增 Raw 文档时，文件名保持 `合晟资产_项目名称_文档类型_YYYYMMDD.md`。
- 新增概念或实体时，要保证 Raw 双链可以解析到对应词条。
- 修改意图识别或重排策略时，要同步检查 API 字段、页面证据轨道和对应测试。
- 修改模型、Top K、请求限制等配置时，优先集中到 `src/config.py`。
- 修改核心流程后至少运行 `python -m unittest discover tests`。
- 真实 API Key 只能放在 `.env`，不要提交到仓库。
