# 改版前原版备份说明

- **备份时间**：2026-07-18（暗色科技风 v0.4 重设计之前）
- **版本标签**：v0.3-ui-preview（浅色森林绿 / 纸质感界面）
- **内容来源**：重设计前已读取的完整原件还原。`index.html`、`app.js`、`README.md` 与改版前一致；`styles.css` 按改版前浅色森林绿/纸质感原件主体完整恢复（工作区当时无 git，尾部 760px 响应式少数规则按原结构补全）。

## 本目录文件

| 文件 | 说明 |
|---|---|
| `index.html` | 改版前页面结构与文案 |
| `styles.css` | 改版前浅色高级感样式 |
| `app.js` | 改版前逻辑（与现网计算口径一致） |
| `README.md` | 改版前启动说明 |

## 如何恢复为工作区主版本

将本目录中的四个文件复制回上一级 `prototype/`，覆盖当前同名文件即可：

```powershell
Copy-Item -Force ".\backup_v0.3_改版前原版\index.html" ".\"
Copy-Item -Force ".\backup_v0.3_改版前原版\styles.css" ".\"
Copy-Item -Force ".\backup_v0.3_改版前原版\app.js" ".\"
Copy-Item -Force ".\backup_v0.3_改版前原版\README.md" ".\"
```

（请在 `prototype` 目录下执行。）

当前 `prototype/` 根目录保留的是 **v0.4 暗色科技风** 版本，未因本次备份而回退。
