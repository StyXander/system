"""W2 冻结的标准股份 DEV_T0 开发资料。

本文件只包含第二周资料包中已技术复核的开发样例；来源仍待团队人工确认。
运行时不读取 Excel，避免用户在浏览器操作时静默改变已测试的字段快照。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


CASE_ID = "STD_DEV_T0"
CASE_NAME = "西安标准工业股份有限公司（标准股份）"
TICKER = "600302"
SOURCE_SNAPSHOT_ID = "std-dev-t0-w2-v0.2"
SOURCE_REVIEW_STATUS = "technical_crosscheck_pending_human_confirmation"

# 每个证据编号始终绑定对应年度自身年报，不能借用下一年度比较列。
EVIDENCE: dict[str, dict[str, Any]] = {
    "STD_REV_2025": {
        "field_kind": "revenue",
        "year": 2025,
        "value": 337238620.57,
        "unit": "元",
        "source_file": "标准股份：标准股份2025年年度报告全文(1).pdf",
        "disclosure_date": "2026-04-30",
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 本期金额列",
        "file_sha256": "CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35",
    },
    "STD_REV_2024": {
        "field_kind": "revenue",
        "year": 2024,
        "value": 446351660.77,
        "unit": "元",
        "source_file": "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        "disclosure_date": "2025-04-29",
        "pdf_page": 67,
        "print_page": 67,
        "locator": "合并利润表 / 本期金额列",
        "file_sha256": "4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09",
    },
    "STD_REV_2023": {
        "field_kind": "revenue",
        "year": 2023,
        "value": 506925296.14,
        "unit": "元",
        "source_file": "标准股份：标准股份2023年年度报告.pdf",
        "disclosure_date": "2024-04-18",
        "pdf_page": 70,
        "print_page": 70,
        "locator": "合并利润表 / 本期金额列",
        "file_sha256": "6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87",
    },
    "STD_REV_2022": {
        "field_kind": "revenue",
        "year": 2022,
        "value": 1050779931.05,
        "unit": "元",
        "source_file": "标准股份：标准股份2022年年度报告.pdf",
        "disclosure_date": "2023-04-19",
        "pdf_page": 63,
        "print_page": 63,
        "locator": "合并利润表 / 本期金额列",
        "file_sha256": "9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8",
    },
    "STD_AR_2025": {
        "field_kind": "accounts_receivable",
        "year": 2025,
        "value": 176388063.66,
        "unit": "元",
        "source_file": "标准股份：标准股份2025年年度报告全文(1).pdf",
        "disclosure_date": "2026-04-30",
        "pdf_page": 59,
        "print_page": 59,
        "locator": "合并资产负债表 / 期末余额列",
        "file_sha256": "CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35",
    },
    "STD_AR_2024": {
        "field_kind": "accounts_receivable",
        "year": 2024,
        "value": 282866689.51,
        "unit": "元",
        "source_file": "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        "disclosure_date": "2025-04-29",
        "pdf_page": 62,
        "print_page": 62,
        "locator": "合并资产负债表 / 期末余额列",
        "file_sha256": "4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09",
    },
    "STD_AR_2023": {
        "field_kind": "accounts_receivable",
        "year": 2023,
        "value": 329742664.91,
        "unit": "元",
        "source_file": "标准股份：标准股份2023年年度报告.pdf",
        "disclosure_date": "2024-04-18",
        "pdf_page": 66,
        "print_page": 66,
        "locator": "合并资产负债表 / 期末余额列",
        "file_sha256": "6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87",
    },
    "STD_AR_2022": {
        "field_kind": "accounts_receivable",
        "year": 2022,
        "value": 439176425.31,
        "unit": "元",
        "source_file": "标准股份：标准股份2022年年度报告.pdf",
        "disclosure_date": "2023-04-19",
        "pdf_page": 59,
        "print_page": 59,
        "locator": "合并资产负债表 / 期末余额列",
        "file_sha256": "9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8",
    },
    # R2 主字段：经营活动产生的现金流量净额。全部取合并现金流量表，不能混用母公司口径。
    "STD_CFO_2025": {
        "field_kind": "operating_cash_flow",
        "year": 2025,
        "value": -32280442.49,
        "unit": "元",
        "source_file": "标准股份：标准股份2025年年度报告全文(1).pdf",
        "disclosure_date": "2026-04-30",
        "pdf_page": 67,
        "print_page": 67,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
        "file_sha256": "CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35",
    },
    "STD_CFO_2024": {
        "field_kind": "operating_cash_flow",
        "year": 2024,
        "value": 1570534.28,
        "unit": "元",
        "source_file": "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        "disclosure_date": "2025-04-29",
        "pdf_page": 71,
        "print_page": 71,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
        "file_sha256": "4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09",
    },
    "STD_CFO_2023": {
        "field_kind": "operating_cash_flow",
        "year": 2023,
        "value": -29688300.25,
        "unit": "元",
        "source_file": "标准股份：标准股份2023年年度报告.pdf",
        "disclosure_date": "2024-04-18",
        "pdf_page": 74,
        "print_page": 74,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
        "file_sha256": "6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87",
    },
    "STD_CFO_2022": {
        "field_kind": "operating_cash_flow",
        "year": 2022,
        "value": 24322281.01,
        "unit": "元",
        "source_file": "标准股份：标准股份2022年年度报告.pdf",
        "disclosure_date": "2023-04-19",
        "pdf_page": 66,
        "print_page": 66,
        "locator": "合并现金流量表 / 经营活动产生的现金流量净额 / 本期金额列",
        "file_sha256": "9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8",
    },
    # 净利润是 R2 的增强项：缺失时主规则仍可判断，但偏差率必须明确显示为不可计算。
    "STD_NP_2025": {
        "field_kind": "net_profit",
        "year": 2025,
        "value": -170193631.28,
        "unit": "元",
        "source_file": "标准股份：标准股份2025年年度报告全文(1).pdf",
        "disclosure_date": "2026-04-30",
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
        "file_sha256": "CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35",
    },
    "STD_NP_2024": {
        "field_kind": "net_profit",
        "year": 2024,
        "value": -165447424.92,
        "unit": "元",
        "source_file": "标准股份：标准股份2024年年度报告全文（修订版）.pdf",
        "disclosure_date": "2025-04-29",
        "pdf_page": 68,
        "print_page": 68,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
        "file_sha256": "4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09",
    },
    "STD_NP_2023": {
        "field_kind": "net_profit",
        "year": 2023,
        "value": -212351971.28,
        "unit": "元",
        "source_file": "标准股份：标准股份2023年年度报告.pdf",
        "disclosure_date": "2024-04-18",
        "pdf_page": 71,
        "print_page": 71,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
        "file_sha256": "6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87",
    },
    "STD_NP_2022": {
        "field_kind": "net_profit",
        "year": 2022,
        "value": -127930543.04,
        "unit": "元",
        "source_file": "标准股份：标准股份2022年年度报告.pdf",
        "disclosure_date": "2023-04-19",
        "pdf_page": 64,
        "print_page": 64,
        "locator": "合并利润表 / 五、净利润 / 本期金额列",
        "file_sha256": "9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8",
    },
}

PERIODS = {
    2025: {"previous_year": 2024, "t0": "2026-04-30"},
    2024: {"previous_year": 2023, "t0": "2025-04-29"},
    2023: {"previous_year": 2022, "t0": "2024-04-18"},
}

RULE_FIELD_SPECS = {
    "R1": (
        ("revenue_current", "本年营业收入", "revenue", "current"),
        ("revenue_previous", "上年营业收入", "revenue", "previous"),
        ("ar_current", "本年应收账款", "accounts_receivable", "current"),
        ("ar_previous", "上年应收账款", "accounts_receivable", "previous"),
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
