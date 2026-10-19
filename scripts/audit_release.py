"""输出可复核交付扫描；只记录命中类别与位置，不打印密钥或个人信息正文。"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.connectivity_facts import project_facts

EXCLUDED = {'.env', '.venv', '.git', '__pycache__', 'runtime', '交付包'}
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'provider_secret': re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),
    'github_secret': re.compile(r'\b(?:ghp|github_pat)_[A-Za-z0-9_]{30,}\b'),
    'email': re.compile(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}'),
    'institution': re.compile(r'(?:大学|学院|指导教师|指导老师)')}


def audit():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    findings, excluded, missing = [], [], []
    for name in filter(None, paths):
        path = Path(name)
        if set(path.parts) & EXCLUDED or path.suffix.lower() == '.pdf':
            excluded.append(name)
            continue
        file = ROOT / name
        if not file.is_file():
            missing.append(name)
            continue
        if path.suffix.lower() not in {'.py', '.md', '.json', '.yaml', '.yml', '.html', '.js', '.css', '.txt'}:
            continue
        text = file.read_text(encoding='utf-8', errors='replace')
        for category, pattern in PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                findings.append({'file': name, 'category': category, 'count': len(matches),
                    'lines': [text.count('\n', 0, match.start()) + 1 for match in matches[:20]],
                    'status': 'requires_context_review' if category in {'email', 'institution'} else 'potential_secret_review'})
    # 依赖审计只报告静态入边，不把动态导入或路由仍引用的代码误删。
    dependencies = {}
    for file in (ROOT / 'backend/app').glob('*.py'):
        tree = ast.parse(file.read_text(encoding='utf-8-sig'))
        dependencies[file.stem] = sorted({node.module.split('.')[0] for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module})
    referenced = {module for modules in dependencies.values() for module in modules}
    report = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'project_facts': project_facts(ROOT), 'scanned_tracked_files': len(paths)-1,
              'findings': findings, 'excluded_from_public_package': excluded, 'missing_files': missing,
              'dependencies': dependencies, 'no_static_relative_inbound': sorted(set(dependencies)-referenced),
              'boundary': '静态扫描不等于无隐私；未审查PDF全文版权或授予开源许可证；无入边不等于可删除',
              'license_decision': 'user_authorized_github_render_owned_changes_20261019_third_party_rights_not_granted'}
    target = ROOT / 'outputs/ai4/repository-audit.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'findings': len(findings), 'missing_files': len(missing), 'project_facts': report['project_facts']}, ensure_ascii=False))


if __name__ == '__main__':
    audit()
