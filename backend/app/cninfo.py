"""巨潮资讯网公开年报适配器。

本模块只负责公开来源发现、公告筛选、PDF 下载和来源级技术校验。
它不负责财务专业判断，也不把搜索结果直接当作审计证据。
公司搜索使用巨潮公开股票清单，公告查询使用巨潮历史公告接口。
年度报告全文与摘要在标题、附件类型和 PDF 内容三层区分。
同一年度存在修订版时保留全部候选，只把最新有效全文作为当前版本。
下载访问限制为巨潮域名，使用低频、有限重试和明确的大小上限。
任何校验失败都返回稳定的错误码，调用方必须停止后续建库。
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx
import fitz


CNINFO_HOME = "https://www.cninfo.com.cn"
CNINFO_STATIC = "https://static.cninfo.com.cn"
ANNOUNCEMENT_QUERY_URL = f"{CNINFO_HOME}/new/hisAnnouncement/query"
# 主页接口负责发现公告，静态域名负责保存公告原件。
# 两个域名都属于巨潮官方来源，其他跳转地址一律不接受。
# 巨潮当前公告列表页对沪、深、北均加载统一的 szse_stock.json。
# 旧教程中的 sse_stock.json、bjse_stock.json 已返回 404，不能继续硬编码。
STOCK_LIST_URLS = {
    "szse": f"{CNINFO_HOME}/new/data/szse_stock.json",
    "sse": f"{CNINFO_HOME}/new/data/szse_stock.json",
    "bjse": f"{CNINFO_HOME}/new/data/szse_stock.json",
}
TRUSTED_HOSTS = {"www.cninfo.com.cn", "static.cninfo.com.cn"}
ANNUAL_CATEGORY = "category_ndbg_szsh;"
# 下载上限用于防止异常响应占满服务内存，最小大小用于排除错误页面。
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
MIN_DOWNLOAD_BYTES = 4 * 1024
# 年报通常远大于十页，页数门槛可以快速拦截空白 PDF 或网页伪装文件。
MIN_PDF_PAGES = 10
MAX_ANNOUNCEMENT_PAGES = 10
REPORT_YEAR_PATTERN = re.compile(r"(?<!\d)(20\d{2})\s*年")
STOCK_CODE_PATTERN = re.compile(r"^\d{6}$")


class CNInfoError(RuntimeError):
    """巨潮适配器的可展示错误；message 不包含密钥、Cookie 或本机路径。"""

    def __init__(self, code: str, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def _safe_text(value: Any) -> str:
    """统一清理巨潮返回的标题、简称和 URL 字段。"""

    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_name(value: str) -> str:
    """名称比较忽略空格、括号和常见公司后缀差异，但不忽略股票代码。"""

    text = _safe_text(value).lower()
    text = re.sub(r"[（）()\[\]【】·,，。\-—_\s]", "", text)
    return text


def _date_from_value(value: Any) -> str:
    """把公告毫秒时间戳或日期文本转换为 ISO 日期。"""

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    text = _safe_text(value)
    match = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", text)
    if not match:
        return text[:10] if re.match(r"^20\d{2}-\d{2}-\d{2}", text) else ""
    return match.group(0).replace("/", "-")


def _report_year_from_title(title: str) -> int | None:
    """只从公告标题识别报告年度，不从下载日期倒推年度。"""

    match = REPORT_YEAR_PATTERN.search(title)
    return int(match.group(1)) if match else None


def _is_trusted_url(value: str, *, static_only: bool = False) -> bool:
    """校验 URL 的协议、主机和路径，防止公告响应带出任意外部地址。"""

    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_HOSTS:
        return False
    if static_only and parsed.hostname != "static.cninfo.com.cn":
        return False
    return parsed.path.lower().endswith(".pdf") if static_only else True


def _market_for_code(code: str) -> str:
    """根据股票代码选择巨潮公告栏目；未知市场不猜测，交给清单解析。"""

    if code.startswith("6"):
        return "sse"
    if code.startswith(("4", "8")):
        return "bjse"
    return "szse"


def _column_and_plate(market: str) -> tuple[str, str]:
    """把股票清单市场映射为历史公告接口需要的栏目参数。"""

    if market == "sse":
        return "sse", "sh"
    if market == "bjse":
        return "bjse", "bj"
    return "szse", "sz"


def _response_json(response: httpx.Response, *, source: str) -> dict[str, Any]:
    """解析 JSON 响应并把上游异常转换成稳定错误。"""

    if response.status_code != 200:
        raise CNInfoError("CNINFO_HTTP_ERROR", f"巨潮{source}请求返回 HTTP {response.status_code}。")
    try:
        payload = response.json()
    except ValueError as error:
        raise CNInfoError("CNINFO_INVALID_JSON", f"巨潮{source}响应不是有效 JSON。") from error
    if not isinstance(payload, dict):
        raise CNInfoError("CNINFO_INVALID_JSON", f"巨潮{source}响应结构不是对象。")
    return payload


def _stock_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容巨潮股票清单的 stockList 外层结构。"""

    rows = payload.get("stockList")
    if rows is None and isinstance(payload.get("data"), dict):
        rows = payload["data"].get("stockList")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _company_from_row(row: dict[str, Any], market: str) -> dict[str, Any] | None:
    """把股票清单的一行规范成案例可保存的公司元数据。"""

    code = _safe_text(row.get("code") or row.get("secCode"))
    name = _safe_text(row.get("zwjc") or row.get("secName") or row.get("name"))
    org_id = _safe_text(row.get("orgId") or row.get("orgID"))
    if not code or not name or not org_id:
        return None
    column, plate = _column_and_plate(market)
    return {
        "ticker": code,
        "company_name": _safe_text(row.get("zwjcFull") or row.get("fullname") or name),
        "company_alias": name,
        "org_id": org_id,
        "market": market,
        "column": column,
        "plate": plate,
        "source_mode": "cninfo_official",
    }


class CNInfoClient:
    """低频访问巨潮公开数据的同步客户端，可注入 MockTransport 做离线测试。"""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        min_delay_seconds: float = 1.0,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        today: date | None = None,
    ) -> None:
        # 默认关闭系统代理，避免代理把官方 PDF 替换成登录页或验证码页面。
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(20.0, timeout_seconds)),
            follow_redirects=True,
            trust_env=False,
            headers={
                "User-Agent": "AuditTrace/0.8 cninfo-official-source-client",
                "Accept": "application/json,text/plain,*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": CNINFO_HOME,
                "Referer": f"{CNINFO_HOME}/new/index",
            },
        )
        self.min_delay_seconds = max(0.0, float(min_delay_seconds))
        self.max_retries = max(0, int(max_retries))
        self._last_request_at = 0.0
        self.today = today or date.today()

    def close(self) -> None:
        """释放本客户端拥有的网络连接。"""

        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "CNInfoClient":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()

    def _wait_before_request(self) -> None:
        """每次请求前等待最小间隔，遇到限流由重试函数额外退避。"""

        wait = self.min_delay_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _request(self, method: str, url: str, *, source: str, **kwargs: Any) -> httpx.Response:
        """统一执行有限重试；403、429和网络错误不会无限重试。"""

        if not _is_trusted_url(url):
            raise CNInfoError("CNINFO_URL_NOT_ALLOWED", f"拒绝访问非巨潮来源：{url}")
        # 每次请求都经过统一节流和有限重试，避免循环查询时形成高频抓取。
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self._wait_before_request()
                response = self.client.request(method, url, **kwargs)
                if response.status_code in {403, 429}:
                    if attempt < self.max_retries:
                        time.sleep(min(8.0, 2.0 ** attempt))
                        continue
                    raise CNInfoError("CNINFO_RATE_LIMITED", f"巨潮{source}请求被限制（HTTP {response.status_code}）。")
                return response
            except CNInfoError:
                raise
            except (httpx.HTTPError, OSError) as error:
                last_error = error
                if attempt < self.max_retries:
                    time.sleep(min(8.0, 2.0 ** attempt))
                    continue
        raise CNInfoError("CNINFO_NETWORK_ERROR", f"巨潮{source}请求失败，已停止重试。") from last_error

    def resolve_company(self, company_query: str) -> dict[str, Any]:
        """用代码或名称解析唯一公司；名称多匹配时返回人工确认状态。"""

        query = _safe_text(company_query)
        if not query:
            raise CNInfoError("COMPANY_QUERY_EMPTY", "企业名称或股票代码不能为空。")
        target_code = query if STOCK_CODE_PATTERN.fullmatch(query) else None
        # 代码可以先按市场缩小范围，名称则需要遍历官方清单后再判定。
        markets: Iterable[str] = (_market_for_code(target_code),) if target_code else ("szse", "sse", "bjse")
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        for market in markets:
            list_url = STOCK_LIST_URLS[market]
            response = self._request("GET", list_url, source="股票清单")
            rows = _stock_rows(_response_json(response, source="股票清单"))
            for raw in rows:
                company = _company_from_row(raw, market)
                if company is None or company["ticker"] in seen:
                    continue
                matched = company["ticker"] == target_code if target_code else (
                    _normalize_name(query) in _normalize_name(company["company_name"])
                    or _normalize_name(query) in _normalize_name(company["company_alias"])
                )
                if matched:
                    matches.append(company)
                    seen.add(company["ticker"])
        # 名称匹配可能产生多个候选，必须把选择权交给人工而不是猜测。
        if not matches:
            raise CNInfoError("COMPANY_NOT_FOUND", f"巨潮股票清单中未找到：{query}")
        if len(matches) > 1:
            raise CNInfoError(
                "COMPANY_AMBIGUOUS",
                "企业名称对应多个巨潮公司候选，需要人工确认。",
                detail={"candidates": matches},
            )
        return matches[0]

    def search_annual_reports(self, company: dict[str, Any], report_year: int) -> list[dict[str, Any]]:
        """查询一个报告年度的年度报告公告，并保留原始元数据的必要字段。"""

        if not 2000 <= int(report_year) <= self.today.year + 1:
            raise CNInfoError("REPORT_YEAR_INVALID", f"报告年度不在允许范围：{report_year}")
        column, plate = _column_and_plate(str(company["market"]))
        payload = {
            "pageNum": "1",
            "pageSize": "30",
            "column": column,
            "tabName": "fulltext",
            "plate": plate,
            "stock": f"{company['ticker']},{company['org_id']}",
            "searchkey": "",
            "secid": "",
            "category": ANNUAL_CATEGORY,
            "trade": "",
            "seDate": f"{report_year + 1}-01-01~{report_year + 2}-12-31",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        # 查询窗口按报告年度后的公告年度设置，避免把披露日期当成报告年度。
        announcements: list[dict[str, Any]] = []
        for page in range(1, MAX_ANNOUNCEMENT_PAGES + 1):
            payload["pageNum"] = str(page)
            response = self._request("POST", ANNOUNCEMENT_QUERY_URL, source="年度报告公告", data=payload)
            body = _response_json(response, source="年度报告公告")
            rows = body.get("announcements") or []
            if not isinstance(rows, list):
                raise CNInfoError("CNINFO_INVALID_ANNOUNCEMENTS", "巨潮公告响应缺少 announcements 列表。")
            announcements.extend(row for row in rows if isinstance(row, dict))
            if not body.get("hasMore") or len(rows) == 0:
                break
        normalized: list[dict[str, Any]] = []
        for row in announcements:
            item = self._normalize_announcement(row, company, report_year)
            if item is not None:
                normalized.append(item)
        return normalized

    def _normalize_announcement(
        self, row: dict[str, Any], company: dict[str, Any], report_year: int
    ) -> dict[str, Any] | None:
        """筛掉摘要、勘误公告和非 PDF 附件，只保留候选全文。"""

        title = _safe_text(row.get("announcementTitle") or row.get("title"))
        inferred_year = _report_year_from_title(title)
        adjunct_url = _safe_text(row.get("adjunctUrl") or row.get("adjunctURL"))
        if not title or inferred_year != report_year or not adjunct_url:
            return None
        title_compact = re.sub(r"\s+", "", title)
        excluded_terms = ("摘要", "英文版", "英文", "更正公告", "勘误公告", "提示性公告", "摘要版")
        if any(term in title_compact for term in excluded_terms):
            return None
        source_url = urljoin(f"{CNINFO_STATIC}/", adjunct_url.lstrip("/"))
        if not _is_trusted_url(source_url, static_only=True):
            return None
        announcement_date = _date_from_value(row.get("announcementTime") or row.get("announcementDate"))
        if not announcement_date:
            announcement_date = _date_from_value(row.get("noticeDate"))
        return {
            "announcement_id": _safe_text(row.get("announcementId")),
            "announcement_title": title,
            "announcement_date": announcement_date,
            "report_year": report_year,
            "ticker": _safe_text(row.get("secCode") or company["ticker"]),
            "company_name": _safe_text(row.get("secName") or company["company_alias"]),
            "org_id": company["org_id"],
            "source_url": source_url,
            "adjunct_type": _safe_text(row.get("adjunctType")),
            "adjunct_size": row.get("adjunctSize"),
            "is_revised": "修订" in title_compact or "更正" in title_compact,
            "raw": {
                key: row.get(key)
                for key in ("announcementId", "announcementTitle", "announcementTime", "adjunctUrl", "adjunctType", "adjunctSize", "secCode", "secName")
                if key in row
            },
        }

    def select_annual_report(self, candidates: list[dict[str, Any]], report_year: int) -> dict[str, Any]:
        """选择最新有效全文；同日期以修订版优先，选择依据写入结果。"""

        valid = [item for item in candidates if item.get("report_year") == report_year]
        if not valid:
            raise CNInfoError("ANNUAL_REPORT_NOT_FOUND", f"未找到 {report_year} 年年度报告全文。")
        valid.sort(
            key=lambda item: (
                item.get("announcement_date") or "0000-00-00",
                bool(item.get("is_revised")),
                item.get("announcement_id") or "",
            ),
            reverse=True,
        )
        chosen = dict(valid[0])
        # 同一年度可能同时存在摘要、正文和修订件，选择依据必须可解释并写入日志。
        chosen["selection_reason"] = "同年度候选按公告日期倒序选择；同日修订版优先。"
        chosen["candidate_count"] = len(valid)
        chosen["candidate_urls"] = [item["source_url"] for item in valid]
        return chosen

    def download_pdf(self, source_url: str) -> tuple[bytes, dict[str, Any]]:
        """下载巨潮 PDF 并校验响应大小、最终 URL 和文件头。"""

        if not _is_trusted_url(source_url, static_only=True):
            raise CNInfoError("PDF_URL_NOT_ALLOWED", "年报下载地址不是巨潮静态 PDF 原件。")
        response = self._request("GET", source_url, source="年报 PDF")
        if response.status_code != 200:
            raise CNInfoError("PDF_HTTP_ERROR", f"年报 PDF 下载返回 HTTP {response.status_code}。")
        final_url = str(response.url)
        if not _is_trusted_url(final_url, static_only=True):
            raise CNInfoError("PDF_REDIRECT_NOT_ALLOWED", "年报 PDF 重定向到了非巨潮地址。")
        content = response.content
        # 先检查响应大小和 PDF 文件头，再交给 PyMuPDF，降低解析异常的影响面。
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise CNInfoError("PDF_TOO_LARGE", "年报 PDF 超过 100MB 安全上限。")
        if len(content) < MIN_DOWNLOAD_BYTES:
            raise CNInfoError("PDF_TOO_SMALL", "年报 PDF 文件过小，疑似错误响应。")
        if not content.startswith(b"%PDF-"):
            raise CNInfoError("PDF_MAGIC_INVALID", "下载内容不是 PDF 文件。")
        digest = hashlib.sha256(content).hexdigest().upper()
        return content, {"final_url": final_url, "byte_count": len(content), "sha256": digest}

    def validate_pdf(
        self,
        content: bytes,
        announcement: dict[str, Any],
        company: dict[str, Any],
        *,
        min_pages: int = MIN_PDF_PAGES,
    ) -> dict[str, Any]:
        """用 PyMuPDF 和前几页文本确认文件属于目标企业和年度报告。"""

        if not content.startswith(b"%PDF-"):
            raise CNInfoError("PDF_MAGIC_INVALID", "待校验内容不是 PDF。")
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as error:
            raise CNInfoError("PDF_PARSE_FAILED", "PDF 无法打开或解析。") from error
        try:
            page_count = len(document)
            if page_count < min_pages:
                raise CNInfoError("PDF_PAGE_COUNT_INVALID", f"PDF 页数过少：{page_count}。")
            # 只读取前几页做身份校验，完整文本留给后续 RAG 建库处理。
            sample_text = "\n".join(document[index].get_text("text") for index in range(min(8, page_count)))
        finally:
            document.close()
        compact = re.sub(r"\s+", "", sample_text).lower()
        company_names = {
            _normalize_name(company.get("company_name", "")),
            _normalize_name(company.get("company_alias", "")),
            _normalize_name(announcement.get("company_name", "")),
        }
        name_hit = any(name and name in compact for name in company_names)
        code_hit = str(company.get("ticker", "")) in compact
        year_hit = f"{announcement['report_year']}年" in compact or str(announcement["report_year"]) in compact
        annual_hit = "年度报告" in compact
        score = sum((name_hit, code_hit, year_hit, annual_hit))
        if score < 3 or not annual_hit:
            raise CNInfoError(
                "PDF_CONTENT_MISMATCH",
                "PDF 内容未能同时确认目标企业、报告年度和年度报告类型。",
                detail={"name_hit": name_hit, "code_hit": code_hit, "year_hit": year_hit, "annual_hit": annual_hit},
            )
        # 返回哈希、页数和命中项，后续案例登记与证据回查只依赖这一份结果。
        return {
            "validation_status": "passed",
            "page_count": page_count,
            "byte_count": len(content),
            "sha256": hashlib.sha256(content).hexdigest().upper(),
            "content_checks": {
                "name_hit": name_hit,
                "code_hit": code_hit,
                "year_hit": year_hit,
                "annual_report_hit": annual_hit,
                "text_sample_chars": len(sample_text),
            },
            "ocr_required": len(sample_text.strip()) < 200,
        }


def prepare_report_years(latest_year: int | None, count: int) -> list[int]:
    """生成从最新年度向前倒推的连续报告年度。"""

    if count < 2 or count > 5:
        raise CNInfoError("REPORT_YEAR_COUNT_INVALID", "年报数量只能是 2 至 5 份。")
    current = latest_year or date.today().year - 1
    if current < 2000:
        raise CNInfoError("REPORT_YEAR_INVALID", "最新报告年度无效。")
    return list(range(current, current - count, -1))
