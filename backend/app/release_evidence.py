"""发布证据的独立重算读取器与外置版本绑定。

设计目的（对应整改项 F02、F03）：

1. 发布门禁原先接收调用方拼好的证据字典，字典里的 `run_record_status`、
   `result_hash_verified`、`human_scores_completed` 等字段是“自报”的。只要谁能
   编辑那份 JSON，就能把未发生的校验写成 verified。本模块改为打开磁盘上的原始
   运行记录，自己重算文件哈希、按同一规则重派生调用 ID、重新执行确定性事实语言
   闸门，并从独立的人工评分台账推导评分完成状态。
2. 版本绑定文件必须落在工作区之外。仓库内的记录不能声明自己的可信性，否则
   “代码改了、记录也跟着改”无法被发现；外置锚点加上真人批准记录才是非循环的信任根。

边界：本模块只证明“记录与磁盘原件一致”，不证明专业判断正确、不证明效果提升，
也不代替真人签字。外置锚点防的是仓库内自报，不防已经能改写本机文件的攻击者。
`human_approval.signature_sha256` 只是把批准人与内容哈希锁在一起的绑定摘要，
不是密码学签名；不可否认性仍需真人自己的密钥签名或纸质签字记录。

2026-09-08 独立验收发现的两处缺口由本模块的 v2 规则关闭（见 A02、A03）：

1. 评分摘要以前只做格式检查，整行内容从不重算，因此“改分不改摘要”会被照单接受；
   现在必须按写入端同一规范重算，并对照**已由真人冻结**的评分标准核对维度与区间。
2. 锚点以前允许空文件表与空运行表，循环里没有待检项也能返回 verified；现在必需
   清单缺项、空表、或锚点未覆盖门禁选用的运行都直接阻断。运行原件里没登记的版本
   值，一律不得由调用方的“预期版本”补写成运行事实。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from .agents import _validate_deterministic_fact_language
from .provider_calls import derive_provider_call_ids
from .schemas import AgentOutput, AgentStep, RuleResult, RunResponse

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIRECTORY = "runs"
RUNTIME_ROOT_RELATIVE = "backend/runtime"
RUN_ID_PATTERN = re.compile(r"^RUN-[A-Z0-9-]{6,64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
# git 提交号是 40 位十六进制，不能拿 64 位的 SHA-256 模式去匹配。
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
# 只有真实完成三角色闭环的状态才算完整链；缺角色、跳过角色都不能补位。
COMPLETED_STEP_STATUSES = frozenset({"complete", "completed", "model_success"})
REQUIRED_ROLES = frozenset({"challenge", "counter", "review"})
# v2：新增必需清单、运行交叉绑定与台账哈希；v1 锚点缺少这些检查，不再受支持。
BINDING_SCHEMA_VERSION = "audittrace_release_binding_v2"
BINDING_VERIFIED = "verified"
BINDING_PENDING_APPROVAL = "pending_human_approval"
# 人工评分标准必须逐版本由真人冻结成文件，读取端只认目录里已冻结的标准。
HUMAN_SCORE_RUBRIC_DIR_RELATIVE = "backend/release_records/human_scores/rubrics"
RUBRIC_SCHEMA_VERSION = "human_score_rubric_v1"
RUBRIC_FROZEN_STATUS = "frozen"
# 版本号会参与文件名拼接，必须先过格式校验，不能当路径片段使用。
RUBRIC_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# 自动化身份一律不接受，避免把 AI 预评分混进真人评分门禁。
AUTOMATED_IDENTITIES = frozenset(
    {"ai", "auto", "automatic", "codex", "qoder", "chatgpt", "gpt", "unknown", "待填写", "tbd", "n/a"}
)
# 一份发布绑定至少要覆盖这些决定发布真伪的源码与记录；缺项即不构成绑定。
REQUIRED_REPO_FILES: tuple[str, ...] = (
    "backend/release_records/current_release.json",
    "backend/release_records/current_evaluation.json",
    "backend/competition_demo_cases.json",
    "backend/app/release_gate.py",
    "backend/app/release_evidence.py",
    "backend/app/provider_calls.py",
    "backend/release_records/human_scores/README.md",
    "backend/release_records/human_scores/rubrics/README.md",
    "scripts/record_human_score.py",
)


def _sha256_bytes(payload: bytes) -> str:
    """文件级 SHA-256，用于把磁盘原件与记录声明的哈希对上。"""

    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    """对同一内容给出稳定哈希：键排序、无多余空白，避免格式化差异误判。"""

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def find_run_record_path(run_id: str, *, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    """在运行目录下定位原始运行记录；找不到或找到多份都直接失败。

    运行编号先做格式校验再参与路径拼接，避免把外部输入当路径穿越使用。命名空间
    子目录（AUDITTRACE_RUNTIME_NAMESPACE）也会一并搜索，但只接受唯一命中。
    """

    if not RUN_ID_PATTERN.fullmatch(str(run_id or "").strip()):
        raise ValueError("运行编号格式不合法")
    normalized = str(run_id).strip()
    runtime_root = (workspace_root / RUNTIME_ROOT_RELATIVE).resolve()
    if not runtime_root.is_dir():
        raise FileNotFoundError("运行目录不存在")
    matches = [path for path in runtime_root.rglob(f"{normalized}.json") if path.parent.name == RUNS_DIRECTORY]
    if not matches:
        raise FileNotFoundError(f"未找到运行记录 {normalized}")
    if len(matches) > 1:
        raise ValueError("同一运行编号存在多份原件，无法确定唯一证据")
    resolved = matches[0].resolve()
    try:
        resolved.relative_to(workspace_root.resolve())
    except ValueError as exc:  # 运行记录被移到工作区外时不承认它是本机证据。
        raise ValueError("运行记录不在工作区内") from exc
    return resolved


def load_run_record(run_id: str, *, workspace_root: Path = WORKSPACE_ROOT) -> tuple[RunResponse, Path, str]:
    """读取并校验原始运行记录，返回模型对象、路径和文件哈希。"""

    path = find_run_record_path(run_id, workspace_root=workspace_root)
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    body = payload.get("run") if isinstance(payload, dict) and isinstance(payload.get("run"), dict) else payload
    run = RunResponse.model_validate(body)
    if run.run_id != str(run_id).strip():
        raise ValueError("运行记录内的 run_id 与文件名不一致")
    return run, path, _sha256_bytes(raw)


def human_score_row_digest(row: Mapping[str, Any]) -> str:
    """人工评分行的绑定摘要：把摘要位置留空后整行规范哈希。

    写入端与读取端必须共用这一实现。历史上两端各自维护了一份哈希规则，
    读取端只核对格式，导致改了分数但保留旧摘要的记录仍被判为有效。
    """

    normalized = dict(row)
    normalized["signed_payload_sha256"] = ""
    return canonical_sha256(normalized)


def load_frozen_rubric(rubric_version: str, rubric_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取某版本的**已由真人冻结**评分标准；缺失、未冻结或格式不合法都返回原因。

    评分标准由谁定、包含哪些维度、上下限是多少都属于专业判断，AI 不代冻结。
    因此这里只认目录里已经写明 `status=frozen` 且 `frozen_by` 是真实姓名的文件。
    """

    version = str(rubric_version or "").strip()
    if not version:
        return None, "缺少评分标准版本 rubric_version"
    if not RUBRIC_VERSION_PATTERN.fullmatch(version):
        return None, f"评分标准版本格式不合法：{version}"
    if not rubric_dir.is_dir():
        return None, f"评分标准目录不存在：{rubric_dir}，需由真人先冻结标准"
    path = rubric_dir / f"{version}.json"
    if not path.is_file():
        return None, f"未找到版本 {version} 的评分标准，需由真人先冻结"
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, f"评分标准文件不可解析：{path.name}"
    if not isinstance(spec, dict):
        return None, f"评分标准文件结构不是对象：{path.name}"
    if spec.get("schema_version") != RUBRIC_SCHEMA_VERSION:
        return None, f"评分标准版本不受支持：{path.name}"
    if str(spec.get("rubric_version") or "").strip() != version:
        return None, f"评分标准文件内的版本号与文件名不一致：{path.name}"
    if str(spec.get("status") or "").strip().lower() != RUBRIC_FROZEN_STATUS:
        return None, f"评分标准 {version} 尚未由真人冻结"
    frozen_by = str(spec.get("frozen_by") or "").strip()
    if not frozen_by or frozen_by.lower() in AUTOMATED_IDENTITIES:
        return None, f"评分标准 {version} 缺少真人冻结人姓名"
    dimensions = spec.get("required_dimensions")
    if not isinstance(dimensions, list) or not dimensions or any(
        not str(item).strip() for item in dimensions
    ) or len({str(item).strip() for item in dimensions}) != len(dimensions):
        return None, f"评分标准 {version} 的必填维度清单不合法"
    score_min, score_max = spec.get("score_min"), spec.get("score_max")
    if not _is_finite_number(score_min) or not _is_finite_number(score_max) or score_min >= score_max:
        return None, f"评分标准 {version} 的分数上下限不合法"
    return spec, None


def _is_finite_number(value: Any) -> bool:
    """有限数值判断：bool 不算数，NaN 与 Infinity 也要挡在评分之外。"""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def load_human_score_record_ids(
    ledger_path: Path,
    run_id: str,
    *,
    rubric_dir: Path | None = None,
) -> tuple[list[str], str | None]:
    """从独立的人工评分台账推导评分记录 ID；任何一项不成立就返回原因而不是猜测。

    人工评分绝不能从运行记录或发布记录自身推导，否则同一份文件既当证据又当结论。
    每行必须：整行重算出的摘要与自身声明一致、绑定同一次运行、评分人真实、
    维度集合与冻结标准完全一致、分数落在标准区间内且为有限数值。
    """

    if rubric_dir is None:
        rubric_dir = WORKSPACE_ROOT / HUMAN_SCORE_RUBRIC_DIR_RELATIVE
    if not ledger_path.is_file():
        return [], "人工评分台账不存在"
    identifiers: list[str] = []
    scorers: set[str] = set()
    rubric_cache: dict[str, tuple[dict[str, Any] | None, str | None]] = {}
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            return [], f"人工评分台账第 {line_number} 行不是合法 JSON"
        if not isinstance(record, dict) or record.get("run_id") != run_id:
            continue
        record_id = str(record.get("record_id") or "").strip()
        location = f"人工评分台账第 {line_number} 行"
        declared = str(record.get("signed_payload_sha256") or "").strip()
        # 先重算再信任：摘要对不上说明行内容在写入后被改过，后面的字段不值得再看。
        if not SHA256_PATTERN.fullmatch(declared) or human_score_row_digest(record) != declared:
            return [], f"{location} 的绑定摘要与整行内容不匹配，疑似写入后被改写"
        if not record_id:
            return [], f"{location} 缺少 record_id"
        scorer = str(record.get("scorer") or "").strip()
        if not scorer or scorer.lower() in AUTOMATED_IDENTITIES:
            return [], f"{location} 缺少真实评分人"
        version = str(record.get("rubric_version") or "").strip()
        if version not in rubric_cache:
            rubric_cache[version] = load_frozen_rubric(version, rubric_dir)
        spec, rubric_error = rubric_cache[version]
        if spec is None:
            return [], f"{location} {rubric_error}"
        scores = record.get("scores")
        if not isinstance(scores, dict):
            return [], f"{location} 分数结构不是对象"
        required = {str(item).strip() for item in spec["required_dimensions"]}
        given = {str(item).strip() for item in scores}
        if given != required:
            missing = "、".join(sorted(required - given)) or "无"
            extra = "、".join(sorted(given - required)) or "无"
            return [], f"{location} 评分维度与冻结标准 {version} 不一致：缺 {missing}；多出 {extra}"
        low, high = float(spec["score_min"]), float(spec["score_max"])
        for dimension, value in scores.items():
            if not _is_finite_number(value) or not low <= float(value) <= high:
                return [], f"{location} 维度 {dimension} 的分数 {value!r} 不是 {low}-{high} 区间内的有限数值"
        identifiers.append(record_id)
        scorers.add(scorer)
    if len(identifiers) < 2 or len(scorers) < 2:
        return [], "人工评分不足两名真人评分者"
    if len(set(identifiers)) != len(identifiers):
        return [], "人工评分记录 ID 重复"
    return identifiers, None


def recompute_posthoc_fact_error(run: RunResponse) -> str | None:
    """对已落盘的模型输出重跑确定性事实语言闸门，复现“事后复核”结论。

    在线运行时该闸门已经执行过一次；这里用同一函数重跑，是为了让评委能证明
    记录里的成功不是只写了个状态字符串。
    """

    rule_by_id: dict[str, RuleResult] = {item.rule_id: item for item in run.rule_results}
    for step in run.agent_steps:
        if not isinstance(step.output, AgentOutput):
            continue
        rule_result = rule_by_id.get(step.output.rule_id)
        if rule_result is None:
            return f"角色 {step.role} 的输出找不到对应规则结果"
        try:
            _validate_deterministic_fact_language(step.output, rule_result)
        except Exception as exc:  # 闸门抛错即视为未通过，保留原因而不是吞掉。
            return f"事实语言闸门复算失败：{type(exc).__name__}: {exc}"
    return None


def build_b3_evidence_from_disk(
    run_id: str,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    human_score_ledger_path: Path | None = None,
    human_rubric_dir: Path | None = None,
    expected_model_id: str | None = None,
    expected_source_commit: str | None = None,
    expected_deployment_commit: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """从磁盘原件重算一份 B3 证据；任何一步不成立都返回 blocked 而不是补全。"""

    provenance: dict[str, Any] = {"run_id": str(run_id), "sources": {}}
    try:
        run, path, file_sha256 = load_run_record(run_id, workspace_root=workspace_root)
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        return {"status": "blocked", "reason": f"原始运行记录不可读：{exc}", "evidence": None, "provenance": provenance}
    provenance["sources"]["run_record"] = {"path": str(path), "sha256": file_sha256}

    steps: list[AgentStep] = list(run.agent_steps or [])
    roles = {step.role for step in steps}
    if roles != REQUIRED_ROLES:
        return {
            "status": "blocked",
            "reason": f"角色集合不是固定的 challenge/counter/review：{sorted(roles)}",
            "evidence": None,
            "provenance": provenance,
        }
    derived_ids = derive_provider_call_ids(steps, run.run_id)
    stored_ids = list(run.provider_call_ids or [])
    if not derived_ids or derived_ids != stored_ids:
        return {
            "status": "blocked",
            "reason": "调用 ID 与逐次尝试哈希重算结果不一致，或缺少可重算的哈希",
            "evidence": None,
            "provenance": {**provenance, "derived_call_ids": derived_ids, "stored_call_ids": stored_ids},
        }
    step_call_total = sum(int(step.provider_call_count or 0) for step in steps)
    if int(run.provider_call_count or 0) != step_call_total or step_call_total != len(derived_ids):
        return {"status": "blocked", "reason": "运行级调用数与角色级调用数不一致", "evidence": None, "provenance": provenance}
    if run.cache_hit is not False:
        return {"status": "blocked", "reason": "缓存回放不得作为新鲜真实模型运行", "evidence": None, "provenance": provenance}
    if run.execution_mode != "external_live":
        return {"status": "blocked", "reason": f"执行模式不是 external_live：{run.execution_mode}", "evidence": None, "provenance": provenance}
    if run.parent_run_id:
        return {"status": "blocked", "reason": "备用或派生运行不能作为新鲜完整链证据", "evidence": None, "provenance": provenance}
    if expected_model_id and run.model_id != expected_model_id:
        return {"status": "blocked", "reason": "运行模型与发布记录目标模型不一致", "evidence": None, "provenance": provenance}
    if run.model_check.status != "model_success":
        return {"status": "blocked", "reason": f"模型自检状态为 {run.model_check.status}", "evidence": None, "provenance": provenance}
    if any(step.status not in COMPLETED_STEP_STATUSES for step in steps):
        return {"status": "blocked", "reason": "存在未完成的 Agent 角色", "evidence": None, "provenance": provenance}

    posthoc_error = recompute_posthoc_fact_error(run)
    context = run.context if isinstance(run.context, dict) else {}
    # 版本只能来自运行发生时登记在原件里的字段；调用方的“预期版本”只用于比较，
    # 不能反向补写成运行事实，否则任何一份旧运行都能被配上新提交冒充新版本。
    original_versions = {
        "source_commit": str(context.get("source_commit") or "").strip().lower(),
        "deployment_commit": str(context.get("deployment_commit") or "").strip().lower(),
        "manifest_sha256": str(context.get("manifest_sha256") or "").strip().lower(),
    }
    expectations = {
        "source_commit": str(expected_source_commit or "").strip().lower(),
        "deployment_commit": str(expected_deployment_commit or "").strip().lower(),
        "manifest_sha256": str(expected_manifest_sha256 or "").strip().lower(),
    }
    for field, expected in expectations.items():
        if not expected:
            continue
        original = original_versions[field]
        if not _matches_pattern(original, SHA256_PATTERN if field == "manifest_sha256" else COMMIT_PATTERN):
            return {
                "status": "blocked",
                "reason": f"运行原件未登记 {field}，调用方提供的预期版本不能补作运行事实",
                "evidence": None,
                "provenance": {**provenance, "version_evidence": original_versions},
            }
        if original != expected:
            return {
                "status": "blocked",
                "reason": f"运行原件登记的 {field} 与当前期望不一致，可能是旧运行配了新提交",
                "evidence": None,
                "provenance": {**provenance, "version_evidence": {**original_versions, "expected": expectations}},
            }
    score_ids, score_error = (
        load_human_score_record_ids(
            human_score_ledger_path,
            run.run_id,
            rubric_dir=human_rubric_dir or (workspace_root / HUMAN_SCORE_RUBRIC_DIR_RELATIVE),
        )
        if human_score_ledger_path is not None
        else ([], "未绑定人工评分台账")
    )
    evidence = {
        "run_id": run.run_id,
        # 以下状态全部由本函数按磁盘原件重算得到，不接受任何外部声明。
        # 三项版本登记值缺一就不能写成 verified，避免常量把不完整记录洗成已核验。
        "run_record_status": (
            "verified"
            if original_versions["source_commit"]
            and original_versions["deployment_commit"]
            and original_versions["manifest_sha256"]
            else "incomplete_record"
        ),
        "environment": str(context.get("environment") or ""),
        "external_live": run.execution_mode == "external_live",
        "provider": str(context.get("provider") or ""),
        "model_id": run.model_id,
        "source_commit": original_versions["source_commit"],
        "deployment_commit": original_versions["deployment_commit"],
        "manifest_sha256": original_versions["manifest_sha256"],
        # 只有原件登记值与外部实际算出的哈希比对通过，才算 manifest 已复核。
        "manifest_hash_verified": bool(
            original_versions["manifest_sha256"]
            and expectations["manifest_sha256"]
            and original_versions["manifest_sha256"] == expectations["manifest_sha256"]
        ),
        "result_sha256": file_sha256,
        "result_hash_verified": bool(file_sha256) and path.is_file(),
        "result_status": run.status,
        "analysis_status": run.run_completeness,
        "completed_roles": len(steps),
        "role_statuses": {step.role: step.status for step in steps},
        "provider_calls": int(run.provider_call_count or 0),
        "provider_call_ids": stored_ids,
        "posthoc_validation_error": posthoc_error,
        "posthoc_validation_status": "failed" if posthoc_error else "passed",
        "human_scores_completed": score_error is None,
        "human_score_record_ids": score_ids,
    }
    provenance["recomputed"] = {
        "provider_call_ids": derived_ids,
        "step_call_total": step_call_total,
        "result_sha256": file_sha256,
        "posthoc_error": posthoc_error,
        "human_score_error": score_error,
        "version_evidence": original_versions,
    }
    return {"status": "loaded", "reason": score_error or posthoc_error or "", "evidence": evidence, "provenance": provenance}


def _matches_pattern(value: str, pattern: re.Pattern[str]) -> bool:
    """格式判断的小工具：空串、缺字段与长度不符一律算不成立，不做猜测补全。"""

    return bool(pattern.fullmatch(str(value or "")))


def _outside_workspace(path: Path, workspace_root: Path) -> bool:
    """锚点必须在工作区之外，否则仓库自己就能改写“外部”证据。"""

    try:
        path.resolve().relative_to(workspace_root.resolve())
    except ValueError:
        return True
    return False


def compute_approval_signature(content_sha256: str, *, approver: str, approved_at: str) -> str:
    """按锚点已固化的内容哈希计算批准摘要。

    批准人和时间必须在生成锚点时就写入，之后只能补这一行摘要；先改内容再补签名
    会让内容哈希自校验失败，这正是防止“事后改写”的机制。
    """

    return hashlib.sha256(
        f"{content_sha256}|{str(approver).strip()}|{str(approved_at).strip()}".encode("utf-8")
    ).hexdigest()


def build_release_binding(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    release_id: str,
    git_head: str,
    tracked_files: list[str],
    run_ids: list[str],
    binding_path: Path,
    approver: str = "",
    approved_at: str = "",
    required_files: Sequence[str] = REQUIRED_REPO_FILES,
    human_score_ledger_path: Path | None = None,
) -> dict[str, Any]:
    """生成外置版本绑定文件；批准人为空时写入待签状态而不是伪造已批。

    清单不能为空：一份没有待检文件的锚点循环起来永远“无漂移”，却什么都没说。
    必需文件缺项同样拒绝生成，避免只绑一个无关文件就宣称完成了版本绑定。
    """

    if not _outside_workspace(binding_path, workspace_root):
        raise ValueError("绑定文件必须位于工作区之外，否则构成自证循环")
    if not COMMIT_PATTERN.fullmatch(str(git_head).strip().lower()):
        raise ValueError("git HEAD 必须是 40 位十六进制提交号")
    normalized_files = [str(item).replace("\\", "/").strip() for item in tracked_files if str(item).strip()]
    normalized_runs = [str(item).strip() for item in run_ids if str(item).strip()]
    if not normalized_files or not normalized_runs:
        raise ValueError("绑定清单不能为空：至少需要一个仓库内文件与一条运行原件")
    missing_required = [relative for relative in required_files if relative not in set(normalized_files)]
    if missing_required:
        raise ValueError("绑定缺少必需文件：" + "、".join(missing_required))
    repo_files = {}
    for relative in normalized_files:
        candidate = (workspace_root / relative).resolve()
        candidate.relative_to(workspace_root.resolve())
        if not candidate.is_file():
            raise FileNotFoundError(f"绑定清单缺少文件：{relative}")
        repo_files[relative.replace("\\", "/")] = _sha256_bytes(candidate.read_bytes())
    run_records = {}
    for run_id in normalized_runs:
        _, path, file_sha256 = load_run_record(run_id, workspace_root=workspace_root)
        run_records[run_id] = {"path": str(path.relative_to(workspace_root)).replace("\\", "/"), "sha256": file_sha256}
    ledger_entry: dict[str, Any] = {}
    if human_score_ledger_path is not None:
        ledger_resolved = human_score_ledger_path.resolve()
        try:
            ledger_relative = str(ledger_resolved.relative_to(workspace_root.resolve())).replace("\\", "/")
        except ValueError as exc:  # 树外台账不能由仓库内锚点声明其哈希，避免路径穿越。
            raise ValueError("人工评分台账必须位于工作区内") from exc
        if not ledger_resolved.is_file():
            raise FileNotFoundError("人工评分台账不存在，无法绑定")
        ledger_entry = {"path": ledger_relative, "sha256": _sha256_bytes(ledger_resolved.read_bytes())}
    payload: dict[str, Any] = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "release_id": str(release_id).strip(),
        "git_head": str(git_head).strip().lower(),
        "required_repo_files": sorted(str(item).replace("\\", "/") for item in required_files),
        "repo_files": repo_files,
        "run_records": run_records,
        # 人工台账一旦进入锚点，改一行评分就会报漂移。
        "human_score_ledger": ledger_entry,
        "human_approval": {
            "approver": str(approver).strip(),
            "approved_at": str(approved_at).strip(),
            # 真人签的是这份内容哈希；先算内容再留空签名位，避免自引用。
            "content_sha256": "",
            "signature_sha256": "",
        },
    }
    payload["human_approval"]["content_sha256"] = canonical_sha256(payload)
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def verify_release_binding(
    binding_path: Path,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    git_head: str | None = None,
    worktree_dirty: bool | None = None,
    expected_run_ids: Sequence[str] | None = None,
    required_files: Sequence[str] = REQUIRED_REPO_FILES,
    expected_human_score_ledger: str | None = None,
) -> dict[str, Any]:
    """重算绑定指向的每个文件，并与外置锚点比对；不一致就报告漂移。

    空清单、缺必需文件、或锚点没有覆盖门禁正在使用的那次运行，都直接判阻断：
    循环里没有待检项时“没有漂移”不等于“证据已绑定”。
    """

    if not _outside_workspace(binding_path, workspace_root):
        return {"status": "blocked", "reason": "绑定文件位于工作区内，不能作为外部信任根"}
    if not binding_path.is_file():
        return {"status": "blocked", "reason": "外置绑定文件不存在"}
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "reason": "外置绑定文件不可解析"}
    if not isinstance(payload, dict) or payload.get("schema_version") != BINDING_SCHEMA_VERSION:
        return {"status": "blocked", "reason": f"外置绑定版本不受支持，当前只接受 {BINDING_SCHEMA_VERSION}"}

    approval = payload.get("human_approval") or {}
    declared_content = str(approval.get("content_sha256") or "")
    unsigned = json.loads(json.dumps(payload, ensure_ascii=False))
    unsigned.get("human_approval", {}).update({"content_sha256": "", "signature_sha256": ""})
    if canonical_sha256(unsigned) != declared_content:
        return {"status": "blocked", "reason": "外置绑定内容与其自报内容哈希不一致，疑似被改写"}

    repo_files = payload.get("repo_files") or {}
    run_records = payload.get("run_records") or {}
    if not isinstance(repo_files, dict) or not repo_files:
        return {"status": "blocked", "reason": "外置绑定的文件清单为空，没有可核验的源码"}
    if not isinstance(run_records, dict) or not run_records:
        return {"status": "blocked", "reason": "外置绑定的运行清单为空，没有可核验的运行原件"}
    declared_required = payload.get("required_repo_files")
    if not isinstance(declared_required, list):
        return {"status": "blocked", "reason": "外置绑定未声明必需文件清单"}
    missing_required = [relative for relative in required_files if relative not in set(repo_files)]
    if missing_required:
        return {"status": "blocked", "reason": "外置绑定缺少必需文件：" + "、".join(missing_required)}
    selected = [str(item).strip() for item in (expected_run_ids or []) if str(item).strip()]
    uncovered = [run_id for run_id in selected if run_id not in set(run_records)]
    if uncovered:
        return {"status": "blocked", "reason": "外置绑定未覆盖门禁选用的运行：" + "、".join(uncovered)}
    declared_ledger = str((payload.get("human_score_ledger") or {}).get("path") or "").replace("\\", "/")
    if expected_human_score_ledger:
        wanted = str(expected_human_score_ledger).strip().replace("\\", "/")
        if declared_ledger != wanted:
            return {"status": "blocked", "reason": f"外置绑定未登记门禁所用的人工评分台账（应为 {wanted}）"}

    drift: list[str] = []
    for relative, expected in repo_files.items():
        candidate = (workspace_root / relative).resolve()
        try:
            candidate.relative_to(workspace_root.resolve())
        except ValueError:
            drift.append(f"{relative} 越出工作区")
            continue
        if not candidate.is_file():
            drift.append(f"{relative} 缺失")
            continue
        if _sha256_bytes(candidate.read_bytes()) != expected:
            drift.append(f"{relative} 哈希已变")
    for run_id, entry in run_records.items():
        try:
            _, _, file_sha256 = load_run_record(run_id, workspace_root=workspace_root)
        except (OSError, ValueError, ValidationError) as exc:
            drift.append(f"{run_id} 原件不可读：{exc}")
            continue
        if file_sha256 != str(entry.get("sha256") or ""):
            drift.append(f"{run_id} 原件哈希已变")
    ledger_entry = payload.get("human_score_ledger") or {}
    if isinstance(ledger_entry, dict) and ledger_entry:
        ledger_relative = str(ledger_entry.get("path") or "")
        ledger_candidate = (workspace_root / ledger_relative).resolve()
        try:
            ledger_candidate.relative_to(workspace_root.resolve())
        except ValueError:
            drift.append("人工评分台账越出工作区")
        else:
            if not ledger_candidate.is_file():
                drift.append("人工评分台账缺失")
            elif _sha256_bytes(ledger_candidate.read_bytes()) != str(ledger_entry.get("sha256") or ""):
                drift.append("人工评分台账哈希已变")
    if drift:
        return {"status": "blocked", "reason": "源码、运行记录或人工台账相对绑定发生漂移：" + "；".join(drift)}

    if not _is_hex(git_head) or str(git_head).lower() != str(payload.get("git_head") or "").lower():
        return {"status": "blocked", "reason": "当前 HEAD 与外置绑定登记的提交不一致"}
    if worktree_dirty is not False:
        return {"status": "blocked", "reason": "工作区未提交变更，绑定快照未冻结"}
    approver = str(approval.get("approver") or "").strip()
    signature = str(approval.get("signature_sha256") or "").strip()
    if not approver or approver.lower() in {"ai", "auto", "unknown", "待填写"}:
        return {"status": BINDING_PENDING_APPROVAL, "reason": "外置绑定缺少真人批准签名", "binding": payload}
    if not SHA256_PATTERN.fullmatch(signature):
        return {"status": BINDING_PENDING_APPROVAL, "reason": "外置绑定批准签名格式无效", "binding": payload}
    expected_signature = compute_approval_signature(
        declared_content, approver=approver, approved_at=str(approval.get("approved_at") or "")
    )
    if signature != expected_signature:
        return {"status": "blocked", "reason": "外置绑定批准签名与内容哈希不匹配"}
    return {"status": BINDING_VERIFIED, "reason": "", "binding": payload}


def _is_hex(value: Any) -> bool:
    """HEAD 只做格式判断，不猜值；None、短串或其他长度都算不可核验。"""

    return bool(COMMIT_PATTERN.fullmatch(str(value or "").strip()))
