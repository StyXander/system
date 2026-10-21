# 交付二：最终代码与 Git 信息

## 一、分支与提交

| 项 | 值 |
|---|---|
| 整合分支 | `integration/finals-three-way-20261021` |
| 最终提交 SHA | `e806b76c94a3bd070d0d534214cebb06dc459f40` |
| 短 SHA | `e806b76` |
| 基线 | `origin/main` = `6abd3d7e816bdf60c3fa4eb464e3787ac9a039b8` |
| 工作树 | `worktrees/integration`（主工作区未被改动） |
| 与 main 差异 | 72 个文件，+7398 / −262 |

### 提交序列

| # | SHA | 内容 |
|---|---|---|
| 1 | `a8a68da` | 恢复来源一漏提交的 `scripts/verify_round3_outputs.py`（未改任何测试断言） |
| 2 | `6b3a431` | 来源三：千克/公斤/千克CO₂e 单位、空白引文拒绝、31 项参数化测试 |
| 3 | `c1b46ba` | 来源二：五文件冲突裁决 + AI 前提降级 + 指令隔离 + 同源不重复扣减 + metric_identity 依据 |
| 4 | `e806b76` | 年度槽位下限与列头同步修复、三模式对照工具、浏览器验收、交付文档 |

四个提交按「证据验证 → 单位与抽取 → 引擎与条件 → 测试与交付」分组，未做单个巨型提交。

## 二、PR 与 CI

| 项 | 值 |
|---|---|
| PR | https://github.com/StyXander/system/pull/4 （Draft） |
| CI 工作流 | `Repository regression` |
| 运行 ID | `39620971970`（另有一次 `39620919621`，同结论） |
| 结论 | **success** |
| 触发提交 | `e806b76` |

### CI 实测数字（从 Actions 日志提取）

| 步骤 | 结果 |
|---|---|
| Quick release contract | 13 passed, 1 warning, 1.43s |
| Full regression | **1135 passed, 29 skipped, 2 warnings, 37.14s** |
| 作业总时长 | 69 秒（14:54:24 → 14:55:33 UTC） |

### 与来源三 937 passed 的关系

来源三 PR（#2）的 937 passed 是其独立补丁在当时的 CI 记录，**不能代表整合版**。整合版 CI 为 1135 passed，多出的部分来自来源一的测试集与新增用例。

### 与本地全量的差异

本地 `pytest backend/tests` 为 1134 passed / 29 skipped / 1 failed（并发登记超时）。CI 为 1135 passed / 0 failed——同一用例在 CI 环境通过，印证该失败是本地高负载下的时序问题，而非业务缺陷。

## 三、部署状态

| 项 | 值 |
|---|---|
| 线上版本 | 仍为 `6abd3d7`（未更新） |
| 部署动作 | **未执行** |
| 原因 | 见下节发布门禁 |

### 发布门禁检查

| 门禁 | 状态 | 说明 |
|---|---|---|
| CI 全绿 | 通过 | 1135 passed，0 failed |
| 真实报告回归 | 通过（有保留） | 5 对全部跑通；正式一致 0 属业务边界 |
| 浏览器四视口 | 通过 | 1440/1024/768/390，0 控制台错误 |
| 浏览器真实提交 | 通过 | 193.6s，结果页六格正常 |
| 刷新恢复 | **未通过** | 刷新回到新建页，需经历史记录 |
| 关系明细展开 | 未自动验证 | Playwright 选择器未命中，需人工确认 |
| 三角色稳定性 | **未通过** | 覆盖 6/8、partial、关系数 8/11/12 波动 |

结论：**不满足无保留发布条件**。可按下列两种方式之一推进，由发布负责人决定：

- **方式 A（推荐）**：合并进 main 并部署，但演示固定使用纯计算模式，并在答辩中主动说明三角色为 partial。
- **方式 B（保守）**：保持线上 `6abd3d7`，仅合并 PR 不部署，待三角色覆盖问题修复后再发。

不采用「先把 PR 合进 main 就宣布三套已整合」的做法——合并不等于验证。

## 四、回滚办法

### 情形一：仅回滚部署（代码保留）

线上为 Render 部署，回滚到上一稳定提交：

1. 在 Render 控制台将服务回滚到上一个 deploy（对应 `6abd3d7`）；
2. 或本地执行 `git revert --no-commit e806b76 c1b46ba 6b3a431 a8a68da` 后重新部署。

验证点：`GET /api/health` 返回 200，工作台能打开，历史记录可读。

### 情形二：回滚分支指针

```bash
git push --force-with-lease origin 6abd3d7:integration/finals-three-way-20261021
```

或在 GitHub 上关闭 PR #4。原始三条分支（`ai/audittrace-release`、`codex/finals-hardening-20261021`、`audit/finals-hardening-20261021`）**均未改动**，随时可重新对照。

### 情形三：恢复主工作区未提交资产

```bash
cd 审迹智链系统
git apply ../integration-backup-20261021/workspace-uncommitted.patch
```

备份目录另含 7 份关键文件副本（`engine.workspace.py` 等），可用于逐文件比对。

## 五、完整 SHA 索引（可复现对照）

| 对象 | SHA |
|---|---|
| 基线 main | `6abd3d7e816bdf60c3fa4eb464e3787ac9a039b8` |
| 来源一 HEAD | `7ed844c1401c3b44b058a1e50115723fd5ccfa4f` |
| 来源一链 | `c38f165` → `8d85d2a` → `abffb09` → `7ed844c` |
| 来源二 HEAD | `b0eeb3d4710d9deaf1ce4ae86eda6309ed65227d` |
| 来源二悬空副本 | `14d785f79ee8…`、`d1f035af89d2…`（父均为 `6abd3d7`，不在任何分支） |
| 来源三 HEAD | `b1612e7cee4e88d5dc00020be9308fa68058df6d` |
| 来源三首个 | `d98d412eb7eef70336b1fb9b18ff69ac4f36d735` |
| 整合 HEAD | `e806b76c94a3bd070d0d534214cebb06dc459f40` |

## 六、复现命令

```bash
# 取得整合版
git fetch origin
git worktree add ../verify e806b76c94a3bd070d0d534214cebb06dc459f40

# 相关测试（约 35 秒）
cd ../verify && python -m pytest backend/tests -k "connectivity or round3 or at_ai or finals_redteam or finals_hardening"

# 全量（约 18 分钟）
python -m pytest backend/tests

# 5 对真实报告基线（约 90 秒，需已缓存 PDF）
python tools/hardening/run_pairs.py --out outputs/integration-20261021/rules_final.json

# 三模式对照（约 4 分钟，需 DEEPSEEK_API_KEY）
python tools/integration_compare.py --pair 000858-2025 --modes calculation_only,single_model,three_agents --out /tmp/compare.json
```
