import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 审迹智链 Web V3 构建配置
// 本地静态预览:开发时 vite dev,构建后可静态部署 dist/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    target: "es2020",
  },
});
