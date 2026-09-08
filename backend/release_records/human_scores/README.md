# 人工评分台账（append-only）

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

本目录保存 B0—B3 对照的**真人**评分记录，每行一条 JSON，只追加不修改。发布门禁
`backend/app/release_evidence.py` 只从这里推导“人工评分是否完成”，不从运行记录或
发布记录里读任何自报布尔值。

## 一行记录必须包含

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `record_id` | 评分记录编号 | 由写入工具生成，重复即拒绝 |
| `run_id` | 被评的那一次运行 | 必须是真实存在的运行编号 |
| `scorer` | 评分人真实姓名 | 不接受 AI、auto、codex、unknown、待填写等自动化身份 |
| `rubric_version` | 本次使用的评分标准版本 | 需由真人先冻结，不能默认套用 |
| `scores` | 逐项分数 | 非空、数值、1—5 分 |
| `blind_form_sha256` | 所填盲评表文件的哈希 | 便于把纸面表与机器记录对上 |
| `signed_payload_sha256` | 行内容与评分人的绑定摘要 | 64 位十六进制 |

## 通过条件

同一次运行需要**至少两名不同真人**的记录，且各自分数非空、签名齐备、`record_id`
不重复。只有一人、同一人重复、分数留空或署名为自动化身份时，门禁保持
`human_scores_completed=false`。

## 写入方式

```
backend/.venv/Scripts/python.exe scripts/record_human_score.py \
    --run-id <RUN-ID> --i-am-human "<真人姓名>" --rubric-version <版本> \
    --score 相关性=4 --score 依据充分性=3 --score 可执行性=4
```

## 当前状态

本目录已建立但**尚无任何评分记录**。B0 未执行，B1/B2/B3 的人工评分为空白，
`PROJECT_STATUS.md` 与发布记录中的 `human_scoring_status` 继续保持 `pending`。
AI 不得代为填写他人评分，也不得用本工具生成看起来完整的记录。
