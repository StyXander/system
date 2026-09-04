"""发布门禁与 B3 真实性判据的生产实现。

这里的规则不得只在测试里存在：判据若写在测试文件内，测试等于自证，真实发布路径
仍然可以被一个可手改的布尔值绕过。缺字段一律判不合格，不接受 ``model_success``
这类裸布尔作为通过依据。
"""

from __future__ import annotations

import re
from typing import Any, Mapping

# 三 Agent 闭环要求三个角色全部完成，缺一个就不是完整链。
REQUIRED_AGENT_ROLES = 3
# 完整 B3 链至少三次供应商真实调用；配置存在或 probe 都不算调用。
MIN_PROVIDER_CALLS = 3
# 真实运行的 run_id 前缀；MOCK、CACHE 等等价前缀一律视为非真实。
RUN_ID_PREFIX = "RUN-"
# 只有生产环境跑出的证据才能进正式对比，本机调试与回放环境不算。
PRODUCTION_ENVIRONMENT = "production"
# 经事后事实闸门复核否定过的历史 run，永久不得复用为正式 B3。
SUPERSEDED_RUN_IDS = frozenset({"RUN-V7-00ED00962F34"})
# commit 必须是完整 40 位十六进制，短哈希不足以唯一绑定版本。
COMMIT_LENGTH = 40
# 结果哈希为 SHA-256 十六进制长度，缺失即证据不可定位。
RESULT_HASH_LENGTH = 64
# 生产证据必须是十六进制字符串，长度检查不能替代内容检查。
HEX_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
HEX_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
# 尚未追加真实模型运行的评估状态，属于未闭合，不得当就绪。
RAW_RECORDS_UNINITIALIZED = "initialized_no_model_runs"
VALID = "valid"
SIGNOFF_APPROVED = "captain_approved_for_competition_demo"
POINTER_VALID = "valid"
COMPLETED_RESULT_STATUSES = frozenset({"complete", "completed", "model_success"})
COMPLETED_ANALYSIS_STATUSES = frozenset({"complete_full_analysis", "completed", "model_success"})


def _as_int(value: Any) -> int:
    """把调用次数安全转成整数：非法或缺失一律按 0，绝不默认放行。"""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _text(value: Any) -> str:
    """统一取字符串形式：None 与空白都算缺失。"""
    return str(value).strip() if value is not None else ""


def _is_hex(value: Any, pattern: re.Pattern[str]) -> bool:
    """严格检查十六进制证据，避免任意重复字符通过长度门槛。"""

    return bool(pattern.fullmatch(_text(value)))


def _is_true(value: Any) -> bool:
    """证据开关必须是真正的布尔 True，字符串和数字不自动放行。"""

    return value is True


def _role_completion_is_valid(evidence: Mapping[str, Any]) -> bool:
    """核对三个角色的逐项完成记录，而不是只信一个总数。"""

    roles = evidence.get("role_statuses")
    if not isinstance(roles, Mapping):
        return False
    return len(roles) == REQUIRED_AGENT_ROLES and all(
        _text(status).lower() in {"complete", "completed", "model_success"}
        for status in roles.values()
    )


def evaluate_b3_eligibility(
    evidence: Mapping[str, Any],
    *,
    expected_model_id: str | None = None,
    expected_source_commit: str | None = None,
    expected_deployment_commit: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> tuple[bool, str]:
    """判断一条运行证据能否作为正式 B3 参与对比。

    绑定项包括真实运行记录、生产环境、外部调用、模型、版本、manifest、结果、
    三角色、事实闸门和真人评分。任一不满足即不合格。
    """
    if not isinstance(evidence, Mapping):
        return False, "B3 证据结构不是对象"
    run_id = _text(evidence.get("run_id"))
    if not re.fullmatch(r"RUN-[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        return False, "缺少有效真实 run_id"
    if run_id in SUPERSEDED_RUN_IDS:
        return False, "该 run 已被事后事实闸门复核否定，不得复用为正式 B3"
    if _text(evidence.get("run_record_status")) != "verified":
        return False, "运行记录未通过可追踪性核验"
    if _text(evidence.get("environment")) != PRODUCTION_ENVIRONMENT:
        return False, "运行环境不是 production"
    if not _is_true(evidence.get("external_live")):
        return False, "没有 external_live 真实生产调用证据"
    if not _text(evidence.get("provider")):
        return False, "缺少真实供应商标识"
    model_id = _text(evidence.get("model_id"))
    if not model_id:
        return False, "缺少模型标识，无法与发布目标模型核对"
    if expected_model_id and model_id != _text(expected_model_id):
        return False, "B3 模型与当前发布目标不一致"
    source_commit = _text(evidence.get("source_commit"))
    deployment_commit = _text(evidence.get("deployment_commit"))
    if not _is_hex(source_commit, HEX_COMMIT_PATTERN):
        return False, "缺少完整 commit，无法与发布证据互相核对"
    if expected_source_commit and source_commit != _text(expected_source_commit):
        return False, "B3 source commit 与当前冻结 HEAD 不一致"
    if not _is_hex(deployment_commit, HEX_COMMIT_PATTERN):
        return False, "缺少完整 deployment commit，无法确认生产版本"
    if expected_deployment_commit and deployment_commit != _text(expected_deployment_commit):
        return False, "B3 deployment commit 与当前生产版本不一致"
    manifest_sha256 = _text(evidence.get("manifest_sha256"))
    if not _is_hex(manifest_sha256, HEX_SHA256_PATTERN):
        return False, "缺少有效 manifest SHA-256"
    if expected_manifest_sha256 and manifest_sha256.lower() != _text(expected_manifest_sha256).lower():
        return False, "B3 manifest 哈希与发布清单不一致"
    result_sha256 = _text(evidence.get("result_sha256"))
    if not _is_hex(result_sha256, HEX_SHA256_PATTERN):
        return False, "缺少有效结果 SHA-256，证据不可定位"
    if not _is_true(evidence.get("manifest_hash_verified")):
        return False, "manifest 哈希尚未由实际文件复核"
    if not _is_true(evidence.get("result_hash_verified")):
        return False, "结果哈希尚未由实际结果文件复核"
    if _text(evidence.get("result_status")).lower() not in COMPLETED_RESULT_STATUSES:
        return False, "B3 结果未达到完整终态"
    if _text(evidence.get("analysis_status")).lower() not in COMPLETED_ANALYSIS_STATUSES:
        return False, "完整分析状态未完成"
    if _as_int(evidence.get("completed_roles")) != REQUIRED_AGENT_ROLES or not _role_completion_is_valid(evidence):
        return False, "三角色未全部完成"
    if _as_int(evidence.get("provider_calls")) < MIN_PROVIDER_CALLS:
        return False, "供应商真实调用次数不足3次"
    call_ids = evidence.get("provider_call_ids")
    if not isinstance(call_ids, (list, tuple)) or len(call_ids) < MIN_PROVIDER_CALLS:
        return False, "缺少三次真实供应商调用的可追踪 ID"
    posthoc_error = _text(evidence.get("posthoc_validation_error"))
    if posthoc_error:
        return False, f"未通过事后事实闸门: {posthoc_error}"
    if _text(evidence.get("posthoc_validation_status")) != "passed":
        return False, "事后事实闸门没有给出 passed 记录"
    if not _is_true(evidence.get("human_scores_completed")):
        return False, "真人评分未完成"
    score_ids = evidence.get("human_score_record_ids")
    if not isinstance(score_ids, (list, tuple)) or not score_ids:
        return False, "缺少真人评分记录 ID"
    return True, VALID


def evaluate_release_ready(
    release_data: Mapping[str, Any],
    evaluation_data: Mapping[str, Any],
    *,
    git_head: str | None,
    worktree_dirty: bool | None,
    human_final_approval: bool,
    deployment_commit: str | None,
    release_evidence_head: str | None,
    manifest_sha256: str | None,
    expected_model_id: str | None,
    signoff_status: str | None,
    b3_evidence: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """判断发布门禁能否打开；任一条不满足即返回不合格并给出原因。

    真人批准必须由调用方显式传入：缺少它时即使其余技术条件全部成立也不得放行。
    本函数不写回任何状态文件，只做判定。
    """
    if not _is_hex(git_head, HEX_COMMIT_PATTERN):
        return False, "当前 HEAD 不可核验，无法冻结发布快照"
    if worktree_dirty is not False:
        return False, "工作区存在未提交变更，发布快照未冻结"

    demo = release_data.get("demo") or {}
    materialized_head = _text(demo.get("materialized_source_head"))
    if not _is_hex(materialized_head, HEX_COMMIT_PATTERN) or materialized_head != _text(git_head):
        return False, "当前 HEAD 与发布快照登记的 materialized_source_head 不一致"

    if not _is_hex(release_evidence_head, HEX_COMMIT_PATTERN) or _text(release_evidence_head) != _text(git_head):
        return False, "release evidence head 与当前 HEAD 不一致或缺失"
    if not _is_hex(deployment_commit, HEX_COMMIT_PATTERN) or _text(deployment_commit) != _text(git_head):
        return False, "deployment commit 与当前 HEAD 不一致或缺失"

    expected_manifest = _text(demo.get("manifest_sha256"))
    if not _is_hex(expected_manifest, HEX_SHA256_PATTERN) or not _is_hex(manifest_sha256, HEX_SHA256_PATTERN):
        return False, "manifest SHA-256 缺失或格式无效"
    if expected_manifest.lower() != _text(manifest_sha256).lower():
        return False, "manifest 实际哈希与发布快照不一致"
    if _as_int(demo.get("case_count")) != 15:
        return False, "发布清单案例数不是冻结的 15 案"

    release_evaluation = release_data.get("evaluation") or {}
    release_evaluation_id = _text(release_evaluation.get("evaluation_id"))
    current_evaluation_id = _text(evaluation_data.get("evaluation_id"))
    if not current_evaluation_id or release_evaluation_id != current_evaluation_id:
        return False, "发布记录与评估记录指向不同的 evaluation_id"

    if _text(evaluation_data.get("pointer_status")) != POINTER_VALID:
        return False, "当前评估指针未通过哈希和 ID 校验"
    current_model_id = _text(evaluation_data.get("model_id"))
    release_model_id = _text((release_data.get("model") or {}).get("model_id"))
    if not _text(expected_model_id) or current_model_id != _text(expected_model_id) or release_model_id != _text(expected_model_id):
        return False, "当前评估、发布记录和目标模型不一致"

    if _text(evaluation_data.get("raw_records_status")) == RAW_RECORDS_UNINITIALIZED:
        return False, "评估尚未追加真实模型运行"
    if _text(evaluation_data.get("human_scoring_status")) != "completed":
        return False, "人工评分未完成"
    if _text(release_evaluation.get("human_scoring_status")) != "completed":
        return False, "发布记录中的人工评分状态未完成"
    if _text(signoff_status) != SIGNOFF_APPROVED:
        return False, "R1 项目队长签字未针对当前源码重新批准"
    b3_valid, b3_reason = evaluate_b3_eligibility(
        b3_evidence or {},
        expected_model_id=expected_model_id,
        expected_source_commit=_text(git_head),
        expected_deployment_commit=_text(deployment_commit),
        expected_manifest_sha256=_text(manifest_sha256),
    )
    if not b3_valid:
        return False, f"新鲜生产 B3 不合格：{b3_reason}"
    if not human_final_approval:
        return False, "缺少真人最终发布批准"
    return True, VALID
