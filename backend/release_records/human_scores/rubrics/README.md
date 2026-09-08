# 人工评分标准冻结目录

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

本目录保存 B0—B3 人工评分所用的**评分标准**。发布门禁读取人工评分时，只认这里
已经由真人冻结的标准文件：`backend/app/release_evidence.py` 的 `load_frozen_rubric`
按 `rubric_version` 定位 `<版本>.json`，标准缺失、未冻结或署名是自动化身份时，
`human_scores_completed` 一律保持 `false`。

## 为什么要有这一层

2026-09-08 独立验收指出：评分台账读取端以前只看 `signed_payload_sha256` 是不是 64
位十六进制，从不重算行内容，也不核对维度与区间。改分不改摘要的记录会被照单接受。
重算能证明"内容没被事后改写"，但"该评哪些维度、几分到几分"是专业判断，只能由人定，
不能由代码或 AI 推定。因此标准本身也要有一份可回查的冻结原件。

## 一个标准文件的字段

```json
{
  "schema_version": "human_score_rubric_v1",
  "rubric_version": "B0B3-RUBRIC-V1",
  "required_dimensions": ["相关性", "依据充分性", "可执行性"],
  "score_min": 1,
  "score_max": 5,
  "status": "frozen",
  "frozen_by": "<真人姓名>",
  "frozen_at": "<冻结时间>"
}
```

| 字段 | 约束 |
| --- | --- |
| `rubric_version` | 与文件名一致；只允许字母、数字、点、下划线和连字符 |
| `required_dimensions` | 非空、不重复；评分行的 `scores` 键集合必须与之**完全相等**，缺项和多评都拒 |
| `score_min` / `score_max` | 有限数值且 `min < max`；分数还必须是该区间内的有限数值，NaN/Infinity/布尔都拒 |
| `status` | 必须是 `frozen`；`draft` 等状态一律不认 |
| `frozen_by` | 真人姓名；AI、auto、codex、qoder、unknown、待填写等一律不认 |

## 当前状态

**本目录尚无任何已冻结标准。** 因此即使两名真人按 `scripts/record_human_score.py`
写入了自洽的评分行，发布门禁仍会报"未找到对应版本的评分标准"，`human_scores_completed`
保持 `false`。这是有意的失败关闭。

## 待真人裁决的一处冲突

盲评表 `artifacts/competition-improvement-20260908/evaluation-instruments/评分表-评分者A.csv`
的表头写作 `相关性得分(0-5) / 依据充分性得分(0-5) / 可执行性得分(0-5)`，而
`backend/release_records/human_scores/README.md` 与历史写入脚本按 **1—5** 校验，
且维度名一个是"依据充分性"、一个是"依据"。冻结标准时必须由人一次性定清：

1. 维度名称与数量（是否就是这三项）；
2. 下限是 0 还是 1；
3. 三人评分表里的"可核验主张数"等计数列是否进入 `scores`。

AI 不代冻结、不代裁决，也不先用一个"看起来合理"的标准把门禁打开。
