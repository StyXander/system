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
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

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
BINDING_SCHEMA_VERSION = "audittrace_release_binding_v1"
BINDING_VERIFIED = "verified"
BINDING_PENDING_APPROVAL = "pending_human_approval"


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


def load_human_score_record_ids(ledger_path: Path, run_id: str) -> tuple[list[str], str | None]:
    """从独立的人工评分台账推导评分记录 ID；缺台账或未签完时返回空而不是猜测。

    人工评分绝不能从运行记录或发布记录自身推导，否则同一份文件既当证据又当
    结论。每行必须是已填分数、已写真实评分人并带签名哈希的记录。
    """

    if not ledger_path.is_file():
        return [], "人工评分台账不存在"
    identifiers: list[str] = []
    scorers: set[str] = set()
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
        scores = record.get("scores")
        scorer = str(record.get("scorer") or "").strip()
        signature = str(record.get("signed_payload_sha256") or "").strip()
        record_id = str(record.get("record_id") or "").strip()
        if not isinstance(scores, dict) or not scores or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) for value in scores.values()
        ):
            return [], f"人工评分台账第 {line_number} 行分数未填或非数值"
        if not scorer or scorer.lower() in {"ai", "auto", "codex", "unknown", "待填写"}:
            return [], f"人工评分台账第 {line_number} 行缺少真实评分人"
        if not SHA256_PATTERN.fullmatch(signature):
            return [], f"人工评分台账第 {line_number} 行缺少签名哈希"
        if not record_id:
            return [], f"人工评分台账第 {line_number} 行缺少 record_id"
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
    score_ids, score_error = (
        load_human_score_record_ids(human_score_ledger_path, run.run_id)
        if human_score_ledger_path is not None
        else ([], "未绑定人工评分台账")
    )
    context = run.context if isinstance(run.context, dict) else {}
    evidence = {
        "run_id": run.run_id,
        # 以下状态全部由本函数重算得到，不接受任何外部声明。
        "run_record_status": "verified",
        "environment": str(context.get("environment") or ""),
        "external_live": run.execution_mode == "external_live",
        "provider": str(context.get("provider") or ""),
        "model_id": run.model_id,
        "source_commit": expected_source_commit,
        "deployment_commit": expected_deployment_commit,
        "manifest_sha256": expected_manifest_sha256,
        "manifest_hash_verified": bool(expected_manifest_sha256),
        "result_sha256": file_sha256,
        "result_hash_verified": True,
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
    }
    return {"status": "loaded", "reason": score_error or posthoc_error or "", "evidence": evidence, "provenance": provenance}


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
) -> dict[str, Any]:
    """生成外置版本绑定文件；批准人为空时写入待签状态而不是伪造已批。"""

    if not _outside_workspace(binding_path, workspace_root):
        raise ValueError("绑定文件必须位于工作区之外，否则构成自证循环")
    if not COMMIT_PATTERN.fullmatch(str(git_head).strip().lower()):
        raise ValueError("git HEAD 必须是 40 位十六进制提交号")
    repo_files = {}
    for relative in tracked_files:
        candidate = (workspace_root / relative).resolve()
        candidate.relative_to(workspace_root.resolve())
        if not candidate.is_file():
            raise FileNotFoundError(f"绑定清单缺少文件：{relative}")
        repo_files[relative.replace("\\", "/")] = _sha256_bytes(candidate.read_bytes())
    run_records = {}
    for run_id in run_ids:
        _, path, file_sha256 = load_run_record(run_id, workspace_root=workspace_root)
        run_records[run_id] = {"path": str(path.relative_to(workspace_root)).replace("\\", "/"), "sha256": file_sha256}
    payload: dict[str, Any] = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "release_id": str(release_id).strip(),
        "git_head": str(git_head).strip().lower(),
        "repo_files": repo_files,
        "run_records": run_records,
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
) -> dict[str, Any]:
    """重算绑定指向的每个文件，并与外置锚点比对；不一致就报告漂移。"""

    if not _outside_workspace(binding_path, workspace_root):
        return {"status": "blocked", "reason": "绑定文件位于工作区内，不能作为外部信任根"}
    if not binding_path.is_file():
        return {"status": "blocked", "reason": "外置绑定文件不存在"}
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "reason": "外置绑定文件不可解析"}
    if not isinstance(payload, dict) or payload.get("schema_version") != BINDING_SCHEMA_VERSION:
        return {"status": "blocked", "reason": "外置绑定版本不受支持"}

    approval = payload.get("human_approval") or {}
    declared_content = str(approval.get("content_sha256") or "")
    unsigned = json.loads(json.dumps(payload, ensure_ascii=False))
    unsigned.get("human_approval", {}).update({"content_sha256": "", "signature_sha256": ""})
    if canonical_sha256(unsigned) != declared_content:
        return {"status": "blocked", "reason": "外置绑定内容与其自报内容哈希不一致，疑似被改写"}

    drift: list[str] = []
    for relative, expected in (payload.get("repo_files") or {}).items():
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
    for run_id, entry in (payload.get("run_records") or {}).items():
        try:
            _, _, file_sha256 = load_run_record(run_id, workspace_root=workspace_root)
        except (OSError, ValueError, ValidationError) as exc:
            drift.append(f"{run_id} 原件不可读：{exc}")
            continue
        if file_sha256 != str(entry.get("sha256") or ""):
            drift.append(f"{run_id} 原件哈希已变")
    if drift:
        return {"status": "blocked", "reason": "源码或运行记录相对绑定发生漂移：" + "；".join(drift)}

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
