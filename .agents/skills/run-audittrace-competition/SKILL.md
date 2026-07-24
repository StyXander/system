---
name: run-audittrace-competition
description: Strictly execute AuditTrace (审迹智链) and 北京市大学生数智会计创新应用竞赛 tasks from the plan/outputs/数智会计竞赛 workspace. Use for plan revisions, teacher-review materials, source verification, audit-rule research, case preparation, prototype planning, future implementation, evaluation, presentations, and any task that must preserve the boundary between proposed work and verified results.
---

# Run AuditTrace Competition

## Start correctly

1. Work only inside the directory containing this skill: `plan/outputs/数智会计竞赛/`.
2. Read `AGENTS.md` and `02_最终确定方案/05_审迹智链_项目方案书_V3_全面复盘修订版.md` before non-trivial work. For implementation status, history, or detailed acceptance criteria, also read the V2.4.4 engineering execution record.
3. For website, visual, interaction, workbench, or presentation tasks, treat the workspace-root `index.html` as the sole main webpage. Edit it and its root `assets/` resources by default. `03_第一周任务与成果/audittrace-local-static/` is an earlier reference prototype, not the current webpage, unless the user explicitly names it.
4. Treat `../../../project/` as an unrelated legacy FINTEL project. Do not read, modify, cite, or reuse it unless the user explicitly requests a separate reuse assessment.
5. State the task type, allowed inputs, intended output, acceptance test, and unresolved human decisions before changing files.

## Preserve the truth boundary

- Treat the current V3 plan as the main proposed design and V2.4.4 as its detailed engineering execution record; neither is proof that a planned feature is implemented.
- Recognize that this workspace has a root display page, local FastAPI and DEV_T0 R1/R2 engineering artifacts, but no frozen formal cases, completed RAG acceptance, or formal experiment.
- Apply source priority: current organizer rules/corrections, then explicit human decisions, then the V3 plan, then the V2.4.4 engineering execution record, then older drafts and AI reviews.
- Never invent sources, page numbers, teacher approvals, cases, data, experiment results, or completed features.
- Use `UNKNOWN` or `待核验` when an original source cannot be checked.
- Keep outputs within audit prescreening: risk clues, normal explanations, evidence gaps, requested materials, and suggested procedures. Do not make fraud findings, audit opinions, or investment recommendations.

## Choose the smallest valid workflow

- Plan or teacher-review task: inspect the exact source sections, make a minimal document change, and keep proposed/approved/implemented states distinct.
- Research task: define the question and source criteria first; verify Gemini or search candidates against originals before citing them.
- Professional-rule task: map each rule to the sales-and-receivables cycle, affected assertion, normal explanation, evidence gap, and follow-up procedure.
- Case-preparation task: inspect availability and dates without exposing future T1 answers; do not select a case without human confirmation.
- Prototype task: edit the root `index.html` when improving the existing main webpage; obtain user approval before creating a separate new prototype directory. Do not redirect work to `project/`.
- Evaluation task: stop if cases, T0, baseline, metric, budget, or human approval are not frozen. Create a simple Research Contract only when the project actually reaches formal experiments.
- Competition-material task: use only verified current facts and label unfinished features as planned.

## Use Gemini safely

- Read `00_Gemini提示词与AI协作流程.md` when preparing Gemini prompts or processing Gemini output.
- Treat Gemini Scout and Critic output as unverified candidates.
- Do not claim Gemini was used unless the user supplies actual output or it was actually used.
- Never send secrets, personal information, client material, or locked T1 to Gemini.
- Return to local originals before changing official claims.

## Finish

Report the files changed, evidence checked, unresolved items, validation performed, and the next human or project gate. Do not commit, publish, deploy, or send external messages without explicit user authorization.
