"""
定位：数据脚本层。
职责：按脚本内配置重新生成合晟资产 Raw 文档、Wiki 词条、总索引和 README。
依赖：本地文件系统、脚本内静态配置和 Markdown 双链规则。
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "Raw"
ENTITY_DIR = ROOT / "Wiki" / "entity"
CONCEPT_DIR = ROOT / "Wiki" / "concept"
INDEX_DIR = ROOT / "data" / "wiki_index"

COMPANY = "合晟资产"
TODAY = date(2026, 7, 22)

DOC_TYPES = [
    "需求规格说明书",
    "技术方案",
    "项目管理计划",
    "系统测试报告",
    "内部验收报告",
]

DEPARTMENTS = {
    "投研管理部": "负责投研数据、组合分析、绩效归因和研究成果沉淀。",
    "风险管理部": "负责风险指标、组合预警、风险处置和压力情景管理。",
    "合规稽核部": "负责合规审查、制度检查、监管留痕和审计抽查。",
    "运营管理部": "负责产品运营、估值复核、清算对账和运营资料归档。",
    "信息技术部": "负责内部系统建设、数据平台、权限体系和运行维护。",
    "财务管理部": "负责预算编制、费用审批、预算占用和执行分析。",
    "质量保障部": "负责测试计划、缺陷管理、回归测试和验收支持。",
}

PEOPLE = {
    "陈明": "信息技术部项目经理，负责项目计划、跨部门协调和上线推进。",
    "李娜": "投研管理部业务负责人，负责投研场景、组合指标和报表口径确认。",
    "王强": "风险管理部业务负责人，负责风险指标、预警规则和处置流程确认。",
    "赵磊": "合规稽核部合规经理，负责合规规则、审计日志和监管口径确认。",
    "周婷": "运营管理部运营经理，负责估值、清算、对账流程确认。",
    "刘洋": "信息技术部架构师，负责接口设计、权限模型和部署方案。",
    "孙敏": "财务管理部财务经理，负责预算口径、费用审批和财务报表确认。",
    "黄涛": "质量保障部测试负责人，负责测试计划、缺陷跟踪和回归测试。",
    "吴静": "产品经理，负责需求规格、原型确认和用户培训材料。",
    "郑凯": "数据工程师，负责数据治理、数据同步和指标口径落地。",
}

TECHS = {
    "Python": "数据处理、批任务和智能问答服务编排。",
    "FastAPI": "内部接口服务和轻量后端能力。",
    "PostgreSQL": "业务数据、配置数据和审计记录存储。",
    "Redis": "会话、热点指标和短周期计算结果缓存。",
    "Kafka": "交易、估值、风控等事件流转。",
    "Vue": "内部管理后台和业务工作台前端。",
    "Docker": "开发、测试和演示环境一致化部署。",
    "Nginx": "反向代理、静态资源和内网访问入口。",
    "Prometheus": "服务指标采集和运行状态监控。",
    "Elasticsearch": "日志检索、文档检索和审计查询。",
    "FAISS": "知识库智能问答系统的本地向量检索。",
    "OpenAI兼容接口": "企业内部智能问答的大模型服务接入。",
}

CONCEPT_DEFINITIONS = {
    "投研": "投资研究过程中的数据收集、观点沉淀、组合分析和决策支持。",
    "投资组合": "由多个资产或产品构成的投资单元，是收益分析和风险监控的基础。",
    "组合管理": "围绕投资组合进行持仓、收益、风险和约束条件管理。",
    "风控": "对投资组合、交易行为和运营流程中的风险进行识别、监控和处置。",
    "风险指标": "用于衡量风险水平的指标，例如集中度、回撤、久期和预警命中次数。",
    "合规": "业务活动符合内部制度、监管要求和审计检查要求。",
    "监管留痕": "对合规审查、客户适当性、交易审批等关键动作保留可追溯记录。",
    "监管报送": "按照监管部门要求提交业务、风险、产品和运营数据。",
    "数据治理": "统一数据标准、指标口径、元数据、质量规则和责任边界。",
    "指标口径": "定义业务指标的计算方式、数据来源、刷新频率和责任人。",
    "权限管理": "控制用户、角色、部门和数据范围之间的访问关系。",
    "权限矩阵": "描述角色、功能、数据范围和审批权限之间的对应关系。",
    "身份认证": "确认访问者身份，并为权限判断提供基础。",
    "单点登录": "统一认证入口，减少重复登录和账号分散管理。",
    "审计日志": "记录用户操作、数据访问、配置变更和系统异常，便于追溯。",
    "数据安全": "关注数据访问、传输、存储、脱敏、审计和权限边界。",
    "数据脱敏": "保护客户、交易、账户和员工等敏感信息。",
    "资产估值": "对基金、组合或资产持仓进行价格确认、估值计算和结果复核。",
    "估值复核": "对估值结果进行二次确认，处理估值差异和说明材料。",
    "清算": "交易成交后的资金、份额、费用和头寸核对处理。",
    "对账": "比较不同来源的数据是否一致，并记录差异处理过程。",
    "资产管理": "围绕产品、组合、投资、运营和风控开展的受托管理活动。",
    "交易指令": "投资经理发起、审批后流转至交易执行环节的标准业务指令。",
    "交易审批": "对交易指令进行权限、风险和合规校验后确认是否放行。",
    "客户适当性": "确认客户风险承受能力与产品风险等级是否匹配。",
    "产品生命周期": "覆盖产品立项、募集、成立、运作、变更、清盘和归档。",
    "产品档案": "记录产品基础信息、风险等级、合同资料、状态和归档材料。",
    "绩效归因": "分析组合收益来源，区分市场、行业、个券和交易贡献。",
    "预算管理": "编制、审批、执行和分析公司费用预算。",
    "费用审批": "对部门费用申请进行预算校验和逐级审批。",
    "知识库": "沉淀制度、项目、技术和业务知识，支持检索和问答。",
    "RAG": "通过检索参考资料后再生成回答，适合企业内部知识问答。",
    "来源引用": "在问答结果中标明答案来自哪些文档，便于人工验证。",
    "接口设计": "定义系统之间的数据字段、认证方式、调用频率和异常处理。",
    "项目管理": "控制范围、进度、成本、质量、风险和沟通。",
    "里程碑": "项目推进中的关键节点，例如需求确认、测试完成和上线验收。",
    "上线": "系统通过验收后进入正式生产使用状态。",
    "验收": "业务、技术和管理方按照约定指标确认项目交付结果。",
    "监控运维": "保障系统运行稳定，及时发现和处理异常。",
    "报表": "按固定口径展示业务、风险、财务和运营数据。",
    "审批流": "把业务申请按角色、条件和金额逐级流转确认。",
    "测试计划": "明确测试范围、测试方法、责任人和通过标准。",
    "缺陷管理": "记录、分级、跟踪和关闭测试或运行中发现的问题。",
    "回归测试": "在修复缺陷或调整功能后重新验证核心流程。",
}

PROJECTS = [
    {
        "name": "投研数据中台",
        "dept": "投研管理部",
        "owner": "李娜",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 180,
        "start": "2025-01-06",
        "period": "2025年1月-2025年5月",
        "summary": "统一沉淀研究数据、组合数据和指标口径，支持投研人员快速生成分析报表。",
        "goals": ["统一研究数据来源", "固化核心投研指标口径", "支持组合分析和报表导出"],
        "modules": ["数据采集", "指标口径管理", "投研报表", "权限矩阵"],
        "techs": ["Python", "PostgreSQL", "Redis", "Vue", "Docker"],
        "concepts": ["投研", "投资组合", "组合管理", "数据治理", "指标口径", "报表", "权限矩阵", "项目管理"],
        "metrics": ["核心指标口径覆盖率达到100%", "常用投研报表生成时间不超过2秒", "权限矩阵覆盖全部投研角色"],
        "test_summary": "本轮重点验证指标计算、组合筛选、报表导出和权限矩阵。",
        "defects": "记录缺陷6个，其中中优先级2个，均为报表筛选条件显示问题，回归测试已通过。",
        "risk": "历史研究表格口径不统一，需由投研管理部在需求阶段完成确认。",
    },
    {
        "name": "组合风控预警平台",
        "dept": "风险管理部",
        "owner": "王强",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 160,
        "start": "2025-02-10",
        "period": "2025年2月-2025年6月",
        "summary": "围绕组合集中度、回撤、久期和异常交易建立日内预警能力。",
        "goals": ["统一风险指标", "支持日内风险预警", "沉淀风险处置记录"],
        "modules": ["风控规则", "预警看板", "处置记录", "风险指标"],
        "techs": ["Python", "Kafka", "PostgreSQL", "Redis", "Prometheus"],
        "concepts": ["风控", "风险指标", "投资组合", "审计日志", "数据安全", "监控运维", "项目管理"],
        "metrics": ["预警数据刷新延迟不超过1分钟", "核心风险规则覆盖率达到95%", "处置记录留痕率达到100%"],
        "test_summary": "本轮重点验证风险规则命中、预警刷新、处置记录和监控指标。",
        "defects": "记录缺陷7个，其中中优先级2个，主要集中在预警看板筛选条件，已完成修复。",
        "risk": "风险规则需要业务负责人逐条确认，避免误报影响投资操作。",
    },
    {
        "name": "资产估值管理系统",
        "dept": "运营管理部",
        "owner": "周婷",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 140,
        "start": "2025-03-03",
        "period": "2025年3月-2025年7月",
        "summary": "规范资产估值、估值复核和估值差异处理流程。",
        "goals": ["统一估值数据入口", "支持估值复核", "输出估值差异报表"],
        "modules": ["估值导入", "估值复核", "差异处理", "估值报表"],
        "techs": ["Python", "PostgreSQL", "Vue", "Nginx", "Docker"],
        "concepts": ["资产估值", "估值复核", "对账", "报表", "审批流", "审计日志", "项目管理"],
        "metrics": ["估值差异识别准确率达到99%", "估值复核流程留痕率达到100%", "估值报表导出时间不超过3秒"],
        "test_summary": "本轮重点验证估值文件导入、差异识别、复核流转和报表导出。",
        "defects": "记录缺陷5个，其中中优先级1个，为估值差异备注未同步显示，已关闭。",
        "risk": "部分非标资产估值规则存在人工判断，需要保留复核说明字段。",
    },
    {
        "name": "产品生命周期管理系统",
        "dept": "运营管理部",
        "owner": "吴静",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 130,
        "start": "2025-04-07",
        "period": "2025年4月-2025年8月",
        "summary": "管理资管产品从立项、募集、运作到清盘归档的全流程。",
        "goals": ["统一产品档案", "固化产品变更审批", "跟踪产品状态"],
        "modules": ["产品立项", "产品档案", "变更审批", "清盘归档"],
        "techs": ["PostgreSQL", "Vue", "FastAPI", "Nginx", "Docker"],
        "concepts": ["产品生命周期", "产品档案", "资产管理", "审批流", "合规", "监管留痕", "项目管理"],
        "metrics": ["产品档案字段完整率达到98%", "产品变更审批留痕率达到100%", "产品状态更新延迟不超过1个工作日"],
        "test_summary": "本轮重点验证产品档案字段、变更审批、状态流转和归档权限。",
        "defects": "记录缺陷4个，均为低优先级界面提示问题，已在回归测试中关闭。",
        "risk": "历史产品档案字段不完整，需要运营管理部先完成数据补录。",
    },
    {
        "name": "客户适当性管理系统",
        "dept": "合规稽核部",
        "owner": "赵磊",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 120,
        "start": "2025-05-06",
        "period": "2025年5月-2025年9月",
        "summary": "校验客户风险承受能力与产品风险等级匹配关系。",
        "goals": ["统一客户风险等级", "校验产品匹配规则", "形成适当性审查记录"],
        "modules": ["客户问卷", "风险等级", "匹配校验", "审查记录"],
        "techs": ["FastAPI", "PostgreSQL", "Redis", "Vue", "Elasticsearch"],
        "concepts": ["客户适当性", "合规", "权限管理", "审计日志", "数据脱敏", "监管留痕", "项目管理"],
        "metrics": ["适当性校验覆盖率达到100%", "客户敏感字段脱敏率达到100%", "审查记录查询时间不超过2秒"],
        "test_summary": "本轮重点验证客户问卷、产品匹配、权限控制和审计查询。",
        "defects": "记录缺陷6个，其中中优先级1个，为历史问卷过期提示不明显，已修复。",
        "risk": "客户历史问卷存在过期情况，需要业务在上线前完成复核。",
    },
    {
        "name": "合规审查工作台",
        "dept": "合规稽核部",
        "owner": "赵磊",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 110,
        "start": "2025-06-02",
        "period": "2025年6月-2025年10月",
        "summary": "为合同、宣传材料、交易事项提供统一合规审查入口。",
        "goals": ["统一审查入口", "配置合规规则", "沉淀审查意见"],
        "modules": ["事项提交", "规则校验", "合规审批", "审计查询"],
        "techs": ["Python", "FastAPI", "PostgreSQL", "Elasticsearch", "Vue"],
        "concepts": ["合规", "审批流", "审计日志", "监管报送", "监管留痕", "数据安全", "项目管理"],
        "metrics": ["常规审查事项平均处理时间缩短30%", "审查意见留痕率达到100%", "审计查询响应时间不超过2秒"],
        "test_summary": "本轮重点验证事项提交、合规规则、审批流和审计查询。",
        "defects": "记录缺陷5个，其中中优先级2个，均已完成修复并通过回归测试。",
        "risk": "不同审查事项规则差异较大，首期只覆盖高频事项。",
    },
    {
        "name": "交易指令管理系统",
        "dept": "投研管理部",
        "owner": "李娜",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 150,
        "start": "2025-07-07",
        "period": "2025年7月-2025年11月",
        "summary": "管理投资经理发起、审批、流转和归档的交易指令。",
        "goals": ["标准化交易指令", "跟踪审批状态", "保留交易留痕"],
        "modules": ["指令录入", "交易审批", "交易流转", "日志归档"],
        "techs": ["FastAPI", "Kafka", "PostgreSQL", "Redis", "Vue"],
        "concepts": ["交易指令", "交易审批", "投研", "审批流", "风控", "审计日志", "项目管理"],
        "metrics": ["交易指令状态同步延迟不超过30秒", "审批流覆盖率达到100%", "指令归档完整率达到100%"],
        "test_summary": "本轮重点验证指令录入、交易审批、状态同步和异常回退。",
        "defects": "记录缺陷8个，其中中优先级2个，主要为审批状态刷新问题，已关闭。",
        "risk": "交易时效要求高，需要在测试阶段重点验证并发和异常回退。",
    },
    {
        "name": "运营清算对账平台",
        "dept": "运营管理部",
        "owner": "周婷",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 125,
        "start": "2025-08-04",
        "period": "2025年8月-2025年12月",
        "summary": "对交易、资金、份额和费用数据进行自动对账和差异处理。",
        "goals": ["自动生成对账结果", "定位清算差异", "跟踪差异处理状态"],
        "modules": ["数据导入", "自动对账", "差异处理", "清算报表"],
        "techs": ["Python", "PostgreSQL", "Kafka", "Vue", "Prometheus"],
        "concepts": ["清算", "对账", "数据治理", "报表", "审计日志", "监控运维", "项目管理"],
        "metrics": ["自动对账覆盖率达到90%", "清算差异定位时间不超过5分钟", "对账报表导出时间不超过3秒"],
        "test_summary": "本轮重点验证对账规则、清算差异、处理状态和报表导出。",
        "defects": "记录缺陷7个，其中中优先级1个，为托管行文件字段提示问题，已修复。",
        "risk": "外部托管行文件格式存在差异，需要保留人工导入模板。",
    },
    {
        "name": "绩效归因分析系统",
        "dept": "投研管理部",
        "owner": "李娜",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 135,
        "start": "2025-09-08",
        "period": "2025年9月-2026年1月",
        "summary": "分析组合收益来源，支持投研复盘和产品月报。",
        "goals": ["计算组合收益贡献", "支持多维归因分析", "生成绩效报表"],
        "modules": ["收益计算", "归因模型", "分析看板", "绩效报表"],
        "techs": ["Python", "PostgreSQL", "Redis", "Vue", "Docker"],
        "concepts": ["绩效归因", "投研", "投资组合", "指标口径", "报表", "数据治理", "项目管理"],
        "metrics": ["绩效归因结果与人工复核差异不超过0.5%", "月报生成时间不超过5分钟", "核心组合覆盖率达到100%"],
        "test_summary": "本轮重点验证收益计算、归因模型、组合筛选和绩效报表。",
        "defects": "记录缺陷6个，其中中优先级1个，为归因维度排序问题，已通过回归测试。",
        "risk": "不同产品策略差异较大，首期归因模型先覆盖标准固收和权益组合。",
    },
    {
        "name": "统一身份认证平台",
        "dept": "信息技术部",
        "owner": "刘洋",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 100,
        "start": "2025-10-13",
        "period": "2025年10月-2026年2月",
        "summary": "统一公司内部系统登录、角色授权和访问审计。",
        "goals": ["统一登录入口", "集中角色权限", "保留访问审计"],
        "modules": ["单点登录", "角色管理", "权限策略", "访问日志"],
        "techs": ["FastAPI", "PostgreSQL", "Redis", "Nginx", "Prometheus"],
        "concepts": ["身份认证", "单点登录", "权限管理", "权限矩阵", "审计日志", "数据安全", "项目管理"],
        "metrics": ["核心系统接入率达到100%", "登录响应时间不超过1秒", "访问日志留存不少于180天"],
        "test_summary": "本轮重点验证登录入口、角色管理、权限策略和访问日志。",
        "defects": "记录缺陷5个，其中中优先级1个，为旧系统跳转参数兼容问题，已修复。",
        "risk": "旧系统账号体系不一致，需要分批接入避免影响日常办公。",
    },
    {
        "name": "财务预算管理系统",
        "dept": "财务管理部",
        "owner": "孙敏",
        "manager": "陈明",
        "tech_lead": "刘洋",
        "budget": 95,
        "start": "2025-11-10",
        "period": "2025年11月-2026年3月",
        "summary": "支持部门预算编制、费用申请、预算占用和执行分析。",
        "goals": ["统一预算口径", "控制费用审批", "生成预算执行报表"],
        "modules": ["预算编制", "费用审批", "预算占用", "执行报表"],
        "techs": ["PostgreSQL", "Vue", "FastAPI", "Redis", "Docker"],
        "concepts": ["预算管理", "费用审批", "审批流", "报表", "权限管理", "审计日志", "项目管理"],
        "metrics": ["费用申请预算校验覆盖率达到100%", "预算执行报表生成时间不超过3秒", "审批记录留痕率达到100%"],
        "test_summary": "本轮重点验证预算编制、费用审批、预算占用和执行报表。",
        "defects": "记录缺陷4个，均为低优先级导出样式问题，已关闭。",
        "risk": "部分部门预算科目口径不同，需要财务管理部统一科目表。",
    },
    {
        "name": "知识库智能问答系统",
        "dept": "信息技术部",
        "owner": "吴静",
        "manager": "陈明",
        "tech_lead": "郑凯",
        "budget": 90,
        "start": "2026-01-05",
        "period": "2026年1月-2026年5月",
        "summary": "把制度、项目文档和操作手册沉淀为可检索、可解释的内部知识库。",
        "goals": ["统一知识入口", "支持语义检索", "展示答案来源"],
        "modules": ["文档入库", "向量检索", "问答生成", "来源展示"],
        "techs": ["Python", "FAISS", "OpenAI兼容接口", "PostgreSQL", "Vue"],
        "concepts": ["知识库", "RAG", "来源引用", "数据治理", "权限管理", "审计日志", "项目管理"],
        "metrics": ["标准问题 Top5 召回命中率达到90%", "回答必须展示来源文档", "知识库更新时间不超过1个工作日"],
        "test_summary": "本轮重点验证文档入库、向量检索、问答生成和来源展示。",
        "defects": "记录缺陷6个，其中中优先级2个，为来源展示排序和空结果提示问题，已修复。",
        "risk": "文档质量会影响问答效果，需要建立入库模板和定期复核机制。",
    },
]


def link(name):
    """把词条名称格式化为 Markdown 双链。"""
    return f"[[{name}]]"


def write(path, text):
    """写入 UTF-8 文本，并确保目标目录存在。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def links_in(text):
    """提取 Markdown 文本中的双链目标，用于统计引用关系。"""
    return [item.split("|", 1)[0].strip() for item in re.findall(r"\[\[([^\]]+)\]\]", text)]


def compact_date(value):
    """把日期格式化为文件名使用的 YYYYMMDD。"""
    return value.strftime("%Y%m%d")


def human_date(value):
    """把日期格式化为文档正文使用的中文日期。"""
    return value.strftime("%Y年%m月%d日")


def project_doc_dates(project):
    """根据项目开始日期生成各类文档日期，保证时间线可复现。"""
    start = datetime.strptime(project["start"], "%Y-%m-%d").date()
    return {
        "需求规格说明书": start,
        "技术方案": start + timedelta(days=21),
        "项目管理计划": start + timedelta(days=35),
        "系统测试报告": start + timedelta(days=98),
        "内部验收报告": start + timedelta(days=126),
    }


def doc_title(project, doc_type, doc_date):
    """生成 Raw 文档基础文件名。"""
    return f"{COMPANY}_{project['name']}_{doc_type}_{compact_date(doc_date)}"


def modules_text(project):
    """把项目模块列表格式化为双链文本。"""
    return "、".join(link(item) for item in project["modules"])


def unique_links(names):
    """按原顺序去重并格式化为双链文本。"""
    unique = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return "、".join(link(name) for name in unique)


def requirement_doc(project, doc_date):
    """生成单个项目的需求规格说明书。"""
    goals = "\n".join(f"{i + 1}. {goal}。" for i, goal in enumerate(project["goals"]))
    def metric_for(i, module):
        if i < len(project["metrics"]):
            return project["metrics"][i]
        return f"{module}操作留痕率达到100%"

    rows = "\n".join(
        f"| REQ-{i + 1:03d} | {module} | 完成{module}相关页面、规则校验、查询和操作留痕 | P0 | {metric_for(i, module)} |"
        for i, module in enumerate(project["modules"])
    )
    concepts = "、".join(link(c) for c in project["concepts"][:4])
    acceptance_participants = unique_links([project["dept"], "信息技术部", "合规稽核部"])
    return f"""
# {link(COMPANY)}{link(project['name'])}需求规格说明书

## 文档元信息
| 项 | 内容 |
| --- | --- |
| 公司 | {link(COMPANY)} |
| 项目名称 | {link(project['name'])} |
| 所属部门 | {link(project['dept'])} |
| 业务负责人 | {link(project['owner'])} |
| 项目经理 | {link(project['manager'])} |
| 编制日期 | {human_date(doc_date)} |
| 项目周期 | {project['period']} |
| 项目预算 | {project['budget']}万元 |

## 1. 项目背景
{link(COMPANY)}需要围绕{concepts}建设可落地的内部系统。{project['summary']}本项目只覆盖首期高频场景，避免范围过大影响{link('验收')}和上线节奏。

## 2. 建设目标
{goals}

## 3. 功能需求
| 编号 | 功能模块 | 需求说明 | 优先级 | 验收指标 |
| --- | --- | --- | --- | --- |
{rows}

## 4. 非功能需求
1. 系统页面常规查询响应时间不超过2秒，批量报表类操作不超过5分钟。
2. 所有关键操作必须写入{link('审计日志')}，日志至少保留180天。
3. 涉及客户、交易、组合或费用数据时必须执行{link('数据脱敏')}、{link('权限管理')}和{link('数据安全')}检查。

## 5. 验收口径
本项目以需求表中的指标作为首期{link('验收')}依据，由{acceptance_participants}共同确认。超出首期范围的需求统一登记为后续迭代事项。
"""


def technical_doc(project, doc_date):
    """生成单个项目的技术方案文档。"""
    tech_list = "、".join(link(t) for t in project["techs"])
    component_rows = "\n".join(
        f"| {link(tech)} | {TECHS[tech]} | {link('信息技术部')} |"
        for tech in project["techs"]
    )
    frontend_line = f"1. 业务人员在{link('Vue')}工作台提交或查询数据。" if "Vue" in project["techs"] else "1. 业务人员在内部业务工作台提交或查询数据。"
    backend = "FastAPI" if "FastAPI" in project["techs"] else "Python"
    cache_line = f"3. 业务数据写入{link('PostgreSQL')}，热点数据写入{link('Redis')}。" if "Redis" in project["techs"] else f"3. 业务数据写入{link('PostgreSQL')}，批处理结果按项目规则归档。"
    monitor_line = f"4. 关键事件进入{link('审计日志')}，运行指标由{link('Prometheus')}采集。" if "Prometheus" in project["techs"] else f"4. 关键事件进入{link('审计日志')}，运行状态纳入{link('监控运维')}巡检。"
    return f"""
# {link(COMPANY)}{link(project['name'])}技术方案

## 文档元信息
| 项 | 内容 |
| --- | --- |
| 公司 | {link(COMPANY)} |
| 项目名称 | {link(project['name'])} |
| 业务牵头部门 | {link(project['dept'])} |
| 技术负责部门 | {link('信息技术部')} |
| 技术负责人 | {link(project['tech_lead'])} |
| 编制日期 | {human_date(doc_date)} |

## 1. 总体设计
{link(project['name'])}采用“前端工作台 + 后端接口 + 数据存储 + 日志审计”的轻量架构。技术选型包括{tech_list}，优先满足可维护、易部署和便于{link('监控运维')}的要求。

## 2. 技术组件
| 组件 | 用途 | 责任部门 |
| --- | --- | --- |
{component_rows}

## 3. 数据流
{frontend_line}
2. 后端服务由{link(backend)}承载，完成{link('身份认证')}、{link('权限管理')}和业务规则校验。
{cache_line}
{monitor_line}

## 4. 安全与接口
系统接口遵循{link('接口设计')}规范，所有内部调用需要携带用户身份信息。涉及敏感字段时执行{link('数据脱敏')}，涉及审批事项时进入{link('审批流')}。
"""


def plan_doc(project, doc_date):
    """生成单个项目的项目管理计划文档。"""
    milestones = [
        ("需求确认", "第1个月", project["owner"]),
        ("技术方案确认", "第2个月", project["tech_lead"]),
        ("核心功能开发", "第3个月", project["manager"]),
        ("测试计划执行", "第4个月", "黄涛"),
        ("上线验收", "最后1个月", project["manager"]),
    ]
    rows = "\n".join(f"| {link('里程碑')}：{name} | {time} | {link(owner)} |" for name, time, owner in milestones)
    return f"""
# {link(COMPANY)}{link(project['name'])}项目管理计划

## 文档元信息
| 项 | 内容 |
| --- | --- |
| 公司 | {link(COMPANY)} |
| 项目名称 | {link(project['name'])} |
| 牵头部门 | {link(project['dept'])} |
| 项目经理 | {link(project['manager'])} |
| 编制日期 | {human_date(doc_date)} |
| 项目周期 | {project['period']} |
| 项目预算 | {project['budget']}万元 |

## 1. 项目范围
本项目采用{link('项目管理')}方式推进，只交付{link(project['name'])}首期能力，覆盖{modules_text(project)}。外部渠道接入、历史系统深度改造和二期自动化能力不纳入首期范围，统一进入后续迭代。

## 2. 里程碑计划
| 里程碑 | 计划时间 | 责任人 |
| --- | --- | --- |
{rows}

## 3. 分工
{link(project['dept'])}负责业务规则和{link('指标口径')}确认，{link('信息技术部')}负责开发、部署和{link('监控运维')}，{link('质量保障部')}负责{link('测试计划')}、{link('缺陷管理')}和{link('回归测试')}，{link('合规稽核部')}负责{link('合规')}检查和{link('审计日志')}抽查。

## 4. 风险管理
主要风险：{project['risk']}应对方式是在需求阶段设立评审清单，由{link(project['owner'])}和{link(project['manager'])}共同签字确认。
"""


def test_doc(project, doc_date):
    """生成单个项目的系统测试报告文档。"""
    metric_rows = "\n".join(f"| TC-{i + 1:03d} | {metric} | 通过 |" for i, metric in enumerate(project["metrics"]))
    return f"""
# {link(COMPANY)}{link(project['name'])}系统测试报告

## 文档元信息
| 项 | 内容 |
| --- | --- |
| 公司 | {link(COMPANY)} |
| 项目名称 | {link(project['name'])} |
| 测试负责人 | {link('黄涛')} |
| 技术负责人 | {link(project['tech_lead'])} |
| 编制日期 | {human_date(doc_date)} |

## 1. 测试范围
测试覆盖{modules_text(project)}。{project['test_summary']}同时验证{link('权限管理')}、{link('审计日志')}、页面响应时间和异常提示。

## 2. 测试结果
| 用例编号 | 验证内容 | 结果 |
| --- | --- | --- |
{metric_rows}

## 3. 缺陷情况
{project['defects']}所有影响{link('上线')}和{link('验收')}的问题已完成修复，并由{link('质量保障部')}完成{link('回归测试')}。

## 4. 测试结论
{link('质量保障部')}认为{link(project['name'])}满足首期上线条件，可以提交{link(project['dept'])}进行业务验收。
"""


def acceptance_doc(project, doc_date):
    """生成单个项目的内部验收报告文档。"""
    metric_rows = "\n".join(f"| {metric} | 达成 | {link(project['owner'])}确认 |" for metric in project["metrics"])
    participants = []
    for name in [project["dept"], "信息技术部", "质量保障部", "合规稽核部"]:
        if name not in participants:
            participants.append(name)
    participant_text = "、".join(link(name) for name in participants)
    return f"""
# {link(COMPANY)}{link(project['name'])}内部验收报告

## 文档元信息
| 项 | 内容 |
| --- | --- |
| 公司 | {link(COMPANY)} |
| 项目名称 | {link(project['name'])} |
| 验收部门 | {link(project['dept'])} |
| 项目经理 | {link(project['manager'])} |
| 验收日期 | {human_date(doc_date)} |

## 1. 验收范围
本次{link('验收')}范围为{link(project['name'])}首期功能，包括{modules_text(project)}。验收依据为需求规格说明书、技术方案、项目管理计划、系统测试报告和上线检查表。

## 2. 验收指标
| 指标 | 结果 | 备注 |
| --- | --- | --- |
{metric_rows}

## 3. 资料归档
项目资料已归档到{link('知识库')}，包括需求、方案、计划、测试和验收五类文档。关键操作满足{link('监管留痕')}要求。后续查阅项目结论时，应优先引用本报告和需求规格说明书，并通过{link('来源引用')}核对出处。

## 4. 验收结论
{participant_text}一致确认：{link(project['name'])}达到首期上线要求，同意进入{link('上线')}和试运行阶段。
"""


DOC_BUILDERS = {
    "需求规格说明书": requirement_doc,
    "技术方案": technical_doc,
    "项目管理计划": plan_doc,
    "系统测试报告": test_doc,
    "内部验收报告": acceptance_doc,
}


def clear_generated_dirs():
    """清理脚本管理的 Raw、Wiki 和索引产物，避免旧数据残留。"""
    for directory in [RAW_DIR, ENTITY_DIR, CONCEPT_DIR]:
        for path in directory.glob("*.md"):
            path.unlink()
    if INDEX_DIR.exists():
        for path in INDEX_DIR.glob("*"):
            if path.is_file():
                path.unlink()


def generate_raw_docs():
    """批量生成 Raw 文档，并返回词条引用统计和实体到文档的反向索引。"""
    doc_links_by_entity = defaultdict(list)
    link_counts = Counter()
    for project in PROJECTS:
        dates = project_doc_dates(project)
        for doc_type in DOC_TYPES:
            doc_date = dates[doc_type]
            if doc_date > TODAY:
                raise ValueError(f"{project['name']} {doc_type} has future date {doc_date}")
            name = doc_title(project, doc_type, doc_date)
            text = DOC_BUILDERS[doc_type](project, doc_date)
            write(RAW_DIR / f"{name}.md", text)
            for item in links_in(text):
                link_counts[item] += 1
                doc_links_by_entity[item].append(name)
    return link_counts, doc_links_by_entity


def entity_description(name):
    """根据实体名称生成实体词条说明。"""
    if name == COMPANY:
        return "公司实体，代表合晟资产内部数字化项目的建设主体和知识库归属方。"
    if name in DEPARTMENTS:
        return DEPARTMENTS[name]
    if name in PEOPLE:
        return PEOPLE[name]
    if name in TECHS:
        return TECHS[name]
    for project in PROJECTS:
        if name == project["name"]:
            return f"内部数字化项目，由{project['dept']}牵头，目标是{project['summary']}"
        if name in project["modules"]:
            return f"{project['name']}中的业务模块，用于支撑首期项目范围和验收核对。"
    return "合晟资产知识库中的业务实体。"


def generate_entities(link_counts, doc_links_by_entity):
    """根据 Raw 双链引用生成实体词条文件。"""
    concept_names = set(CONCEPT_DEFINITIONS)
    for name, count in sorted(link_counts.items()):
        if name in concept_names:
            continue
        docs = sorted(set(doc_links_by_entity[name]))
        doc_lines = "\n".join(f"- [[{doc}]]" for doc in docs)
        text = f"""
# {name}

- 类型：实体
- 所属知识库：[[{COMPANY}]]
- 出现次数：{count} 次

## 说明
{entity_description(name)}

## 关联文档
{doc_lines}
"""
        write(ENTITY_DIR / f"{name}.md", text)


def generate_concepts():
    """根据概念配置生成概念词条文件。"""
    for name, desc in CONCEPT_DEFINITIONS.items():
        text = f"""
# {name}

- 类型：概念
- 所属知识库：[[{COMPANY}]]

## 说明
{desc}

## 在本项目中的用途
该概念用于连接合晟资产内部项目文档、业务规则、验收指标和问答证据，便于 RAG 检索时同时利用语义内容和 Wiki 双链关系。
"""
        write(CONCEPT_DIR / f"{name}.md", text)


def generate_index(link_counts):
    """生成 Wiki 总索引，汇总项目、部门、概念、实体和 Raw 文档。"""
    entity_names = sorted(path.stem for path in ENTITY_DIR.glob("*.md"))
    concept_names = sorted(path.stem for path in CONCEPT_DIR.glob("*.md"))
    raw_names = sorted(path.stem for path in RAW_DIR.glob("*.md"))
    project_lines = "\n".join(f"- [[{project['name']}]]：{project['summary']}" for project in PROJECTS)
    dept_lines = "\n".join(f"- [[{name}]]：{desc}" for name, desc in DEPARTMENTS.items())
    concept_lines = "\n".join(f"- [[{name}]]" for name in concept_names)
    entity_lines = "\n".join(f"- [[{name}]] ({link_counts.get(name, 0)})" for name in entity_names)
    raw_lines = "\n".join(f"- [[{name}]]" for name in raw_names)
    text = f"""
# {COMPANY} - 内部数字化项目知识库

> 本知识库收录{COMPANY}内部数字化项目资料，围绕投研、风控、合规、运营、财务和信息技术场景组织，适合用于 LLM Wiki / RAG 问答演示。

---

## 知识库概览

| 类别 | 数量 |
| --- | --- |
| 原始文档 (Raw) | 60 |
| 内部项目 | 12 |
| 每个项目文档数 | 5 |
| 概念词条 (concept) | {len(concept_names)} |
| 实体词条 (entity) | {len(entity_names)} |
| 牵头部门 | {len(DEPARTMENTS)} |

---

## 公司主体

- [[{COMPANY}]]

## 部门索引

{dept_lines}

## 项目索引

{project_lines}

## 核心概念

{concept_lines}

## 实体索引

{entity_lines}

## 全部原始文档

{raw_lines}
"""
    write(ROOT / "Wiki" / "index.md", text)


def generate_readme():
    """生成与当前知识库范围一致的 README。"""
    project_names = "、".join(f"`{p['name']}`" for p in PROJECTS)
    text = f"""
# {COMPANY}内部 Wiki 智能问答系统

这是一个面向{COMPANY}内部数字化项目文档的 LLM Wiki / RAG 问答演示系统。项目将 Markdown 原始文档、概念词条和实体词条统一构建为本地知识库，通过 `FAISS` 向量检索和 `NetworkX` 语义关联图谱进行混合召回，再调用通义千问大模型生成严格基于参考资料的中文回答。

当前数据集刻意保持简单、完整、可验证：系统内置 **12 个内部数字化项目**，每个项目固定包含 5 类文档，总计 60 份 Raw 文档。文档日期均不晚于 2026年7月22日，方便人工核对答案来源。

```text
合晟资产内部项目 -> Markdown 双链词条 -> 本地索引构建 -> 混合检索召回 -> Prompt 组装 -> LLM 回答 -> 页面可解释展示
```

## 当前版本 2.1：合晟资产可验证知识库

1. 系统内置 60 份内部项目文档，覆盖需求规格、技术方案、项目管理计划、系统测试报告和内部验收报告。
2. 项目范围聚焦 12 个业务系统：{project_names}。
3. 实体词条覆盖公司、部门、项目、人员、技术组件和业务模块，不压缩实体，确保双链都可追溯。
4. 概念词条覆盖投研、投资组合、风控、合规、数据治理、权限矩阵、审计日志、资产估值、估值复核、绩效归因、客户适当性、RAG、来源引用、测试计划、缺陷管理等核心概念。
5. 检索阶段同时使用语义相似度和 Wiki 双链图谱，适合演示“实体关系 + 语义召回”的企业知识库问答思路。
6. 页面会展示最终回答、命中的图谱关键词、关联原始文档、完整 Prompt 和 Top 5 检索切片，方便验证答案来源。

## 目录结构

| 路径 | 作用 |
| --- | --- |
| `server.py` | Python 标准库 HTTP 服务入口，提供静态页面和问答 API |
| `web/` | 原生 HTML、CSS、JavaScript 前端页面 |
| `src/wiki_engine.py` | 核心问答引擎，负责建库、检索、重排和生成 |
| `Raw/` | 60 份合晟资产内部项目 Markdown 文档 |
| `Wiki/index.md` | 知识库总览 |
| `Wiki/concept/` | 概念词条库 |
| `Wiki/entity/` | 实体词条库 |
| `data/wiki_index/` | 本地索引产物目录，重新建库后生成 |
| `scripts/regenerate_hesheng_kb.py` | 合晟资产示例知识库生成脚本 |
| `tests/test_hesheng_kb_integrity.py` | 知识库一致性和内容质量校验 |

## 本地启动

```bash
pip install -r requirements.txt
python server.py
```

启动后访问：

```text
http://127.0.0.1:8000
```

如果 `data/wiki_index/` 为空，请在页面左侧点击“重建本地索引”。

## 推荐演示问题

```text
简单验证：投研数据中台的验收指标有哪些？
中等难度：组合风控预警平台使用了哪些技术组件，各自承担什么作用？
高难度：对比客户适当性管理系统和合规审查工作台在权限、审计和监管留痕上的设计差异。
```

## 验证命令

```bash
python -m unittest tests.test_hesheng_kb_integrity -v
python -m unittest tests.test_server_api -v
python -m py_compile server.py src/wiki_engine.py scripts/regenerate_hesheng_kb.py
```

## 面试讲解重点

这个版本的重点不是数据量大，而是结构清楚：12 个项目、5 类文档、完整双链实体和概念。用户提问后，可以从检索切片和 Prompt 中快速验证答案是否来自知识库，体现企业 RAG 项目的可解释性、可维护性和可评估性。
"""
    write(ROOT / "README.md", text)


def main():
    """执行完整知识库重建流程。"""
    clear_generated_dirs()
    generate_concepts()
    link_counts, doc_links_by_entity = generate_raw_docs()
    generate_entities(link_counts, doc_links_by_entity)
    generate_index(link_counts)
    generate_readme()
    print("Generated Hesheng Asset knowledge base:")
    print(f"- Raw docs: {len(list(RAW_DIR.glob('*.md')))}")
    print(f"- Entity pages: {len(list(ENTITY_DIR.glob('*.md')))}")
    print(f"- Concept pages: {len(list(CONCEPT_DIR.glob('*.md')))}")
    print("- Local wiki index files removed; rebuild from the web page when needed.")


if __name__ == "__main__":
    main()
