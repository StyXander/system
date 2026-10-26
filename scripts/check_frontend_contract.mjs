import { readFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// 检查恢复后的双塔首页与绿色工作台实际加载的资源。
const root = new URL('../', import.meta.url);
const html = readFileSync(new URL('index.html', root), 'utf8');
const failures = [];
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
if (new Set(ids).size !== ids.length) failures.push('入口存在重复元素ID');
const scripts = [...html.matchAll(/<script\b[^>]*\bsrc="([^"?]+)(?:\?[^"]*)?"/g)].map(m => m[1]);
const styles = [...html.matchAll(/<link\b[^>]*\bhref="([^"?]+\.css)(?:\?[^"]*)?"/g)].map(m => m[1]);
for (const resource of [...scripts, ...styles]) {
  if (!resource.startsWith('/assets/')) {
    failures.push(`入口资源未绑定本地assets: ${resource}`);
    continue;
  }
  const path = new URL(resource.slice(1), root);
  if (!existsSync(path)) {
    failures.push(`入口资源缺失: ${resource}`);
    continue;
  }
  if (resource.endsWith('.js')) {
    const result = spawnSync(process.execPath, ['--check', fileURLToPath(path)], {encoding: 'utf8'});
    if (result.status !== 0) failures.push(`脚本语法错误: ${resource}: ${result.stderr}`);
  }
}
for (const required of ['connectivity.js', 'connectivity-status.js', 'connectivity-workspace.js', 'redesign-home.js', 'ambient.js']) {
  if (!scripts.some(path => path.endsWith('/' + required))) failures.push(`当前工作台缺少 ${required}`);
}
for (const requiredId of ['redesign-home', 'world-left', 'world-right', 'model-left', 'model-right', 'connectivity-root', 'cn-workspace']) {
  if (!ids.includes(requiredId)) failures.push(`恢复页面缺少 ${requiredId}`);
}
if (scripts.some(path => /connectivity-shell\.js$/.test(path)) || styles.some(path => /\/workbench(?:-polish)?\.css$/.test(path))) {
  failures.push('恢复页面仍在加载被撤回的重构资源');
}
// 业务状态由tests/frontend的行为测试核验；此处只验证入口和实际资源。
if (failures.length) {
  console.error(failures.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`frontend contract ok: ${ids.length} unique ids, ${scripts.length} scripts, ${styles.length} styles`);
}
