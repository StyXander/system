"""公告日期公共边界：不推测缺失日期，旧模型读取保持兼容。"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import re


def normalize_disclosure_date(value):
    if value is None or not str(value).strip():
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        if isinstance(value, (int, float)) or re.fullmatch(r"\d{10,13}", text):
            numeric = float(value)
            return datetime.fromtimestamp(numeric / 1000 if abs(numeric) >= 100_000_000_000 else numeric,
                                          tz=ZoneInfo("Asia/Shanghai")).date().isoformat()
        match = re.fullmatch(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?", text)
        if match:
            return date(*map(int, match.groups())).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    raise ValueError("INVALID_DISCLOSURE_DATE")


def document_date_issue(doc, as_of_date=None):
    raw = doc.disclosure_date
    try:
        normalized = normalize_disclosure_date(raw)
        code = "MISSING_DISCLOSURE_DATE" if not normalized else (
            "FUTURE_DISCLOSURE_DATE" if as_of_date and normalized > str(as_of_date) else "")
    except ValueError:
        code = "INVALID_DISCLOSURE_DATE"
    if not code:
        return None
    reasons = {"MISSING_DISCLOSURE_DATE": "发布日期未登记，需核实公告日期或取消选择",
               "INVALID_DISCLOSURE_DATE": "发布日期格式或历法日期无效，需核实公告元数据",
               "FUTURE_DISCLOSURE_DATE": "发布日期晚于观察截至日，请取消选择或明确调整观察时点"}
    return {"code": code, "document_id": doc.document_id, "company": doc.company,
            "period": doc.effective_period, "report_type": doc.report_type,
            "raw_value": raw, "message": reasons[code]}
