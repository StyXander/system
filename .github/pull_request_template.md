## 改了什么

<!-- 一句话说明本 PR 的目标。多个不相关改动请拆成多个 PR。 -->

## 为什么

<!-- 对应 Issue 编号或具体场景。涉及核对规则时请写明判定条件与依据。 -->

## 变更类型

- [ ] 缺陷修复
- [ ] 新功能
- [ ] 核对规则 / 口径判定
- [ ] 文档
- [ ] CI / 工程

## 测试

<!-- 粘贴实际执行的命令与结果。跳过（skipped）的用例请单独说明原因，不得算作通过。 -->

```bash
python -m pytest backend/tests/test_release_contract.py -q
python -m pytest -q
node --test tests/frontend/connectivity-status.test.mjs
```

结果：

-
-

## 对现有合同的影响

- [ ] 无影响
- [ ] 修改了结果合同 / 导出格式（`backend/app/connectivity_schemas.py` 等），已在下方说明兼容性

<!-- 涉及合同变更时，请说明旧结果是否仍可读取、导出字段是否新增或改名。 -->

## 安全与数据

- [ ] 本 PR 不包含 `.env`、API Key、Token、真实企业内部资料或第三方报告 PDF
- [ ] 不涉及把 `unknown` / `not_comparable` 等不确定性标注改写为确定性结论

## 部署影响

<!-- 是否需要重新部署、是否新增环境变量、是否影响 Render 配置。无影响请写"无"。 -->
