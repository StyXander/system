# 人工评分台账（append-only）

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

本目录保存 B0—B3 对照的**真人**评分记录，每行一条 JSON，只追加不修改。发布门禁
`backend/app/release_evidence.py` 只从这里推导“人工评分是否完成”，不从运行记录或
发布记录里读任何自报布尔值。

## 一行记录必须包含

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `record_id` | 评分记录编号 | 由写入工具生成，重复即拒绝 |
| `run_id` | 被评的那一次运行 | 必须是真实存在的运行编号；整行摘要绑定它，改运行即摘要失配 |
| `scorer` | 评分人真实姓名 | 不接受 AI、auto、codex、qoder、unknown、待填写等自动化身份 |
| `rubric_version` | 本次使用的评分标准版本 | 必须指向 `rubrics/<版本>.json` 中**已由真人冻结**的标准 |
| `scores` | 逐项分数 | 键集合必须与标准的必填维度完全相等，值必须是标准区间内的有限数值 |
| `blind_form_sha256` | 所填盲评表文件的哈希 | 可留空；填写时必须是 64 位十六进制 |
| `signed_payload_sha256` | 整行内容的绑定摘要 | 64 位十六进制，由 `release_evidence.human_score_row_digest` 计算 |

## 通过条件

同一次运行需要**至少两名不同真人**的记录，且每行满足：

1. 读取端把 `signed_payload_sha256` 位置留空后整行重算，结果必须与该行声明一致——
   改分数而保留旧摘要会被直接拒绝；
2. `rubric_version` 指向的标准文件存在、`status=frozen`、`frozen_by` 是真人姓名；
3. `scores` 的维度集合与标准必填维度完全一致，每项分数落在标准规定的上下限内且为有限数值；
4. `record_id` 非空且不重复，评分人不是自动化身份。

任一条件不成立时，门禁保持 `human_scores_completed=false`。摘要验证只能证明内容绑定，
不代替真人身份认定，也不证明专业评分正确。

## 写入方式

```
backend/.venv/Scripts/python.exe scripts/record_human_score.py \
    --run-id <RUN-ID> --i-am-human "<真人姓名>" --rubric-version <已冻结的版本号> \
    --score 相关性=4 --score 依据充分性=3 --score 可执行性=4
```

## 当前状态

本目录已建立但**尚无任何评分记录**，`rubrics/` 下也**尚无任何已冻结标准**。B0 未执行，
B1/B2/B3 的人工评分为空白，`PROJECT_STATUS.md` 与发布记录中的 `human_scoring_status`
继续保持 `pending`。AI 不得代为填写他人评分、不得代为冻结评分标准，也不得用本工具
生成看起来完整的记录。
