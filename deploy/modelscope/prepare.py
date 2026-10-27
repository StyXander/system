"""按运行文件白名单构建魔搭部署目录，不带密钥、全文 PDF 或本机运行数据。"""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tmp" / "modelscope-deploy" / "repo"
TEXT = {".py", ".js", ".css", ".json", ".jsonl", ".html", ".txt", ".md", ".csv", ".yaml", ".yml", ".sql"}
SECRET = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|ms-[a-f0-9]{8}-[a-f0-9-]{27,}|github_pat_[A-Za-z0-9_]{30,}|ghp_[A-Za-z0-9]{30,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})\b")


def main() -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = {ROOT / p for p in tracked if p and (
        p.startswith("backend/app/") or p.startswith("assets/official-v4/")
        or (p.startswith("backend/") and "/" not in p[len("backend/"):])
        or (p.startswith("backend/release_records/") and Path(p).suffix in {".json", ".jsonl"})
        or (p.startswith("backend/demo_cases/") and Path(p).suffix == ".json")
        or (p.startswith("outputs/evaluation_") and Path(p).suffix in {".json", ".csv"})
        or p in {"index.html", "PROJECT_STATUS.json", "PROJECT_AUTHORIZATION.json", "backend/__init__.py"}
    )}
    # 发布只取已登记到 Git 的运行文件，避免把本机临时 JSON 或素材带入公网。
    # 有未提交的运行修改时先阻止打包；提交后再与精确快照分别核验。
    runtime_paths = [p.relative_to(ROOT).as_posix() for p in files]
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *runtime_paths], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    copied = {}
    TARGET.mkdir(parents=True, exist_ok=True)
    for path in sorted(files):
        if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        if path.suffix.lower() in TEXT and SECRET.search(content.decode("utf-8", errors="replace")):
            raise ValueError(f"密钥扫描阻断：{relative}")
        if len(content) > 100 * 1024 * 1024:
            raise ValueError(f"超出普通 Git 文件限制：{relative}")
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied[relative] = hashlib.sha256(content).hexdigest()
    required_demo = {
        "backend/demo_cases/baosteel_zhanjiang.json",
        "backend/app/connectivity_project_demo.py",
        "assets/official-v4/baosteel-demo.js",
        "assets/official-v4/baosteel-demo.css",
    }
    missing_demo = required_demo - set(copied)
    if missing_demo:
        raise ValueError("宝钢专项运行文件没有完整进入部署包：" + ", ".join(sorted(missing_demo)))
    for name in ["Dockerfile", "app.py", ".dockerignore", ".gitattributes"]:
        shutil.copy2(Path(__file__).parent / name, TARGET / name)
        copied[name] = hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
    canonical = json.dumps(copied, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "source_snapshot_sha256": hashlib.sha256(canonical).hexdigest(),
        "source_baseline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "files": copied,
        "boundary": "运行文件来自该 Git 提交的干净工作区；部署包原始字节快照与 Git 提交分别核验。",
        "ai_generated_content_notice": "AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。",
    }
    (TARGET / "deployment-source.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (TARGET / "README.md").write_text("---\nsdk: docker\napp_port: 7860\n---\n\n# 审迹智链 AuditTrace\n\n面向股东、公众投资者、环保组织和研究机构的年度报告与可持续发展报告关联核对。先判断比较前提，再计算同值、组成、比例和多位置关系，沿原文查找差异解释。专业人员可查看完整明细。\n\nAI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。\n", encoding="utf-8")
    (TARGET / ".gitignore").write_text(".env\n**/__pycache__/\n**/runtime/\n.venv/\n", encoding="utf-8")
    print(json.dumps({"file_count": len(copied), "source_snapshot_sha256": manifest["source_snapshot_sha256"], "total_bytes": sum((TARGET / p).stat().st_size for p in copied), "secret_scan": "passed", "path": str(TARGET)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
