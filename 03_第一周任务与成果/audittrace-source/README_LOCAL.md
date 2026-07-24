# 审迹智链 AuditTrace - 本地开发说明

这是当前已发布网页的完整可编辑源码包。项目使用 React 19、TypeScript/TSX、Vinext 和普通 CSS 实现；并不是单个静态 HTML 文件。

## 主要文件

- `app/page.tsx`：页面 HTML 结构、文字内容和交互逻辑。
- `app/globals.css`：颜色、字体、间距、圆角、组件、动画和响应式样式。
- `app/layout.tsx`：网页标题、描述、语言和全局布局。
- `public/favicon.svg`：网站图标。
- `package.json`：依赖和本地开发命令。
- `.openai/hosting.json`：ChatGPT Sites 项目标识；只在继续使用 Sites 发布时需要。

## 本地运行

请先安装 Node.js 22.13 或更高版本，然后在项目根目录运行：

```bash
npm ci
npm run dev
```

终端会显示本地访问地址，通常是 `http://localhost:5173`。

## 生成正式构建

```bash
npm run build
```

## 修改建议

1. 修改页面内容或增加交互：编辑 `app/page.tsx`。
2. 调整配色、字号、间距或响应式断点：编辑 `app/globals.css`。
3. 新增图片：放入 `public/`，然后使用 `/文件名` 引用。
4. 新增复杂功能时，可在 `app/components/` 下拆分 React 组件。

## 说明

- 源码包未包含 `node_modules`、构建缓存、部署产物和 Git 历史，因此文件较小。
- 原型中的“待导入”“待替换”“待验证”是有意保留的真实状态提示，避免将占位数据表现为审计分析结果。
- 当前版本对应首次发布的响应式官网与三步交互原型。
