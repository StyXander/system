"""W2 冻结的标准股份 DEV_T0 开发资料。

本文件只包含第二周资料包中已技术复核的开发样例；来源仍待团队人工确认。
运行时不读取 Excel，避免用户在浏览器操作时静默改变已测试的字段快照。
冻结样例服务离线回归和界面演示，不代表已形成正式审计底稿。
样例企业、证券代码和案例编号在此集中定义，避免模块间名称漂移。
来源快照编号随技术复核批次变化，旧运行仍保留原编号用于复验。
来源复核状态明确写为待人工确认，页面不得把技术核对显示为批准。
每个年度只登记选定的年报全文，摘要不能作为财务字段来源。
修订版年报以公告标题明确标记，不能和原版共享模糊来源描述。
披露日期决定对应运行时点，晚于时点的报告不能回填较早分析。
官方链接只用于回到巨潮原件，不代表仓库取得年报再分发许可。
整份文件哈希用于确认下载副本，页码定位不能替代文件身份校验。
文件名只用于本地登记，任何读取仍应受工作区和案例目录边界限制。
营业收入字段取合并利润表本期金额，不能借用下一年比较列。
应收账款字段取合并资产负债表列示额，并明确保存净额计量基础。
当前样例没有把应收票据和合同资产合并进 R1 主字段口径。
坏账准备变化可能影响净额，因此报告必须继续展示这一口径限制。
经营现金流字段取合并现金流量表，不能混入母公司现金流数据。
净利润只是 R2 增强项，缺失时不得编造现金流利润偏差指标。
负数金额保持原始符号，不能为便于展示而转换为绝对值。
所有金额统一保存为人民币元，规则层无需执行隐含单位换算。
证据编号同时编码字段类别和年度，防止跨年引用看似相同的数值。
文档编号包含年度和哈希前缀，使同年度修订版仍能区分来源身份。
PDF 页码和印刷页码分别保留，二者相同时也不能省略字段含义。
定位说明指出报表和列名，避免只给页码却无法快速回查具体金额。
期间表只开放具备连续上年比较的年度，不为单独年度生成伪比较。
每个时点采用当期年报披露日，不能统一替换成代码运行日期。
规则字段规格决定当前值和上年值映射，调用方不能自行交换期间。
R1 与 R2 共享营业收入时只生成一条来源，避免同一事实重复计数。
字段去重以运行内字段编号为准，不以金额相等推断它们属于同一事实。
未知规则编号直接失败，不能静默退回默认规则掩盖调用错误。
不支持的当前年度直接抛出缺键，避免返回不完整的空字段上下文。
返回前复制证据字典，调用方修改运行字段不会污染冻结常量。
案例上下文只包含来源与期间身份，不在数据层预先写入风险判断。
标准案例与自动导入案例最终使用同一规则接口，样例不享有放宽校验。
新增年度必须同时补齐来源元数据、必要字段和连续期间映射。
修改冻结金额必须附带新的来源复核记录和快照版本，不能原地悄改。
本文件的确定性数值只证明程序可复现，不证明专业阈值已经获批。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


CASE_ID = "STD_DEV_T0"
CASE_NAME = "西安标准工业股份有限公司（标准股份）"
TICKER = "600302"
SOURCE_SNAPSHOT_ID = "std-dev-t0-w2-v0.2"
SOURCE_REVIEW_STATUS = "technical_crosscheck_pending_human_confirmation"

# 官方公告标题、披露日、全文 URL 和文件哈希在此只登记一次。
# 字段证据只引用该年度元数据，避免同一年报的 URL 在多个财务字段间漂移。
ANNUAL_REPORT_SOURCES: dict[int, dict[str, str]] = {
    2025: {
        "announcement_title": "标准股份：标准股份2025年年度报告全文",
        "source_file": "标准股份：标准股份2025年年度报告全文(1).pdf",
        "disclosure_date": "2026-04-30",
        "source_url": "https://static.cninfo.com.cn/finalpage/2026-04-30/1225266733.PDF",
        "file_sha256": "CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35",
    },
    2024: {
        "announcement_title": "标准股份：标准股份2024年年度报告全文（修订版）",
        "source_file": "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        "disclosure_date": "2025-04-29",
        "source_url": "https://static.cninfo.com.cn/finalpage/2025-04-29/1223359539.PDF",
        "file_sha256": "4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09",
    },
    2023: {
        "announcement_title": "标准股份：标准股份2023年年度报告",
        "source_file": "标准股份：标准股份2023年年度报告.pdf",
        "disclosure_date": "2024-04-18",
        "source_url": "https://static.cninfo.com.cn/finalpage/2024-04-18/1219646140.PDF",
        "file_sha256": "6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87",
    },
    2022: {
        "announcement_title": "标准股份：标准股份2022年年度报告",
        "source_file": "标准股份：标准股份2022年年度报告.pdf",
        "disclosure_date": "2023-04-19",
        "source_url": "https://static.cninfo.com.cn/finalpage/2023-04-19/1216455382.PDF",
        "file_sha256": "9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8",
    },
}

# 每个证据编号始终绑定对应年度自身年报，不能借用下一年度比较列。
EVIDENCE: dict[str, dict[str, Any]] = {
    "STD_REV_2025": {
        "field_kind": "revenue",
        "year": 2025,
        "value": 337238620.57,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2025],
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 本期金额列",
    },
    "STD_REV_2024": {
        "field_kind": "revenue",
        "year": 2024,
        "value": 446351660.77,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2024],
        "pdf_page": 67,
        "print_page": 67,
        "locator": "合并利润表 / 本期金额列",
    },
    "STD_REV_2023": {
        "field_kind": "revenue",
        "year": 2023,
        "value": 506925296.14,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2023],
        "pdf_page": 70,
        "print_page": 70,
        "locator": "合并利润表 / 本期金额列",
    },
    "STD_REV_2022": {
        "field_kind": "revenue",
        "year": 2022,
        "value": 1050779931.05,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2022],
        "pdf_page": 63,
        "print_page": 63,
        "locator": "合并利润表 / 本期金额列",
    },
    "STD_AR_2025": {
        "field_kind": "accounts_receivable",
        "year": 2025,
        "value": 176388063.66,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2025],
        "pdf_page": 59,
        "print_page": 59,
        "locator": "合并资产负债表 / 期末余额列",
    },
    "STD_AR_2024": {
        "field_kind": "accounts_receivable",
        "year": 2024,
        "value": 282866689.51,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2024],
        "pdf_page": 62,
        "print_page": 62,
        "locator": "合并资产负债表 / 期末余额列",
    },
    "STD_AR_2023": {
        "field_kind": "accounts_receivable",
        "year": 2023,
        "value": 329742664.91,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2023],
        "pdf_page": 66,
        "print_page": 66,
        "locator": "合并资产负债表 / 期末余额列",
    },
    "STD_AR_2022": {
        "field_kind": "accounts_receivable",
        "year": 2022,
        "value": 439176425.31,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2022],
        "pdf_page": 59,
        "print_page": 59,
        "locator": "合并资产负债表 / 期末余额列",
    },
    # R2 主字段：经营活动产生的现金流量净额。全部取合并现金流量表，不能混用母公司口径。
    "STD_CFO_2025": {
        "field_kind": "operating_cash_flow",
        "year": 2025,
        "value": -32280442.49,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2025],
        "pdf_page": 67,
        "print_page": 67,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
    },
    "STD_CFO_2024": {
        "field_kind": "operating_cash_flow",
        "year": 2024,
        "value": 1570534.28,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2024],
        "pdf_page": 71,
        "print_page": 71,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
    },
    "STD_CFO_2023": {
        "field_kind": "operating_cash_flow",
        "year": 2023,
        "value": -29688300.25,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2023],
        "pdf_page": 74,
        "print_page": 74,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
    },
    "STD_CFO_2022": {
        "field_kind": "operating_cash_flow",
        "year": 2022,
        "value": 24322281.01,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2022],
        "pdf_page": 66,
        "print_page": 66,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
    },
    # 净利润是 R2 的增强项：缺失时主规则仍可判断，但偏差率必须明确显示为不可计算。
    "STD_NP_2025": {
        "field_kind": "net_profit",
        "year": 2025,
        "value": -170193631.28,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2025],
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
    },
    "STD_NP_2024": {
        "field_kind": "net_profit",
        "year": 2024,
        "value": -165447424.92,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2024],
        "pdf_page": 68,
        "print_page": 68,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
    },
    "STD_NP_2023": {
        "field_kind": "net_profit",
        "year": 2023,
        "value": -212351971.28,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2023],
        "pdf_page": 71,
        "print_page": 71,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
    },
    "STD_NP_2022": {
        "field_kind": "net_profit",
        "year": 2022,
        "value": -127930543.04,
        "unit": "元",
        **ANNUAL_REPORT_SOURCES[2022],
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
    },
}

PERIODS = {
    2025: {"previous_year": 2024, "t0": "2026-04-30"},
    2024: {"previous_year": 2023, "t0": "2025-04-29"},
    2023: {"previous_year": 2022, "t0": "2024-04-18"},
}

RULE_FIELD_SPECS = {
    # 当前工程读取的是合并资产负债表“应收账款”列示金额（净额/账面价值口径），
    # 不是专业草案拟扩展的应收账款账面余额、应收票据与合同资产合计口径。
    "R1": (
        ("revenue_current", "本年营业收入", "revenue", "current"),
        ("revenue_previous", "上年营业收入", "revenue", "previous"),
        ("ar_current", "本年应收账款（报表列示额）", "accounts_receivable", "current"),
        ("ar_previous", "上年应收账款（报表列示额）", "accounts_receivable", "previous"),
    ),
    "R2": (
        ("revenue_current", "本年营业收入", "revenue", "current"),
        ("revenue_previous", "上年营业收入", "revenue", "previous"),
        ("operating_cash_flow_current", "本年经营活动现金流量净额", "operating_cash_flow", "current"),
        ("operating_cash_flow_previous", "上年经营活动现金流量净额", "operating_cash_flow", "previous"),
        ("net_profit_current", "本年净利润（R2增强项）", "net_profit", "current"),
    ),
}

EVIDENCE_PREFIX = {
    "revenue": "REV",
    "accounts_receivable": "AR",
    "operating_cash_flow": "CFO",
    "net_profit": "NP",
}


def get_period_sources(current_year: int, rule_ids: tuple[str, ...] = ("R1",)) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """按所选规则组装字段，重复字段只保留一条来源记录供程序校验和网页回查。"""
    if current_year not in PERIODS:
        raise KeyError(current_year)

    period = PERIODS[current_year]
    previous_year = period["previous_year"]
    requested_specs = []
    for rule_id in rule_ids:
        requested_specs.extend(RULE_FIELD_SPECS[rule_id])

    rows: list[dict[str, Any]] = []
    seen_field_ids: set[str] = set()
    for field_id, label, kind, position in requested_specs:
        if field_id in seen_field_ids:
            continue
        seen_field_ids.add(field_id)
        year = current_year if position == "current" else previous_year
        evidence_id = f"STD_{EVIDENCE_PREFIX[kind]}_{year}"
        row = deepcopy(EVIDENCE[evidence_id])
        row.update(
            {
                "evidence_id": evidence_id,
                "field_id": field_id,
                "field_label": label,
                "document_id": f"STD-AR-{year}-{row['file_sha256'][:12]}",
                "storage_relpath": row["source_file"],
                "currency": "CNY",
                "statement_scope": "合并",
                "field_basis": "net" if kind == "accounts_receivable" else "reported",
                "source_review_status": SOURCE_REVIEW_STATUS,
            }
        )
        rows.append(row)

    context = {
        "case_id": CASE_ID,
        "company_name": CASE_NAME,
        "ticker": TICKER,
        "current_year": current_year,
        "previous_year": previous_year,
        "t0": period["t0"],
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_review_status": SOURCE_REVIEW_STATUS,
    }
    return context, rows
