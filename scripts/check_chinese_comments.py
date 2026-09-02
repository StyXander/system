"""检查 backend/app 的中文注释与独立说明性 docstring 行占比。"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "backend" / "app"
CHINESE = re.compile(r"[\u3400-\u9fff]")
MIN_RATIO = 0.10


def _docstring_lines(tree: ast.AST) -> set[int]:
    result: set[int] = set()
    candidates = [tree, *(node for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))]
    for node in candidates:
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            result.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return result


def inspect_file(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    nonempty = {number for number, line in enumerate(lines, start=1) if line.strip()}
    explanatory: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and len(CHINESE.findall(token.string)) >= 4:
            explanatory.add(token.start[0])
    try:
        docstrings = _docstring_lines(ast.parse(text, filename=str(path)))
    except SyntaxError as error:
        raise RuntimeError(f"无法解析 {path}: {error}") from error
    for number in docstrings:
        if number <= len(lines) and len(CHINESE.findall(lines[number - 1])) >= 4:
            explanatory.add(number)
    return len(nonempty), len(explanatory & nonempty)


def main() -> int:
    total_nonempty = 0
    total_explanatory = 0
    details: list[tuple[str, int, int]] = []
    for path in sorted(SOURCE_DIR.glob("*.py")):
        nonempty, explanatory = inspect_file(path)
        total_nonempty += nonempty
        total_explanatory += explanatory
        details.append((path.name, explanatory, nonempty))
    ratio = total_explanatory / total_nonempty if total_nonempty else 0.0
    for name, explanatory, nonempty in details:
        print(f"{name}: {explanatory}/{nonempty}")
    print(f"TOTAL: {total_explanatory}/{total_nonempty} = {ratio:.2%}; required >= {MIN_RATIO:.0%}")
    if ratio < MIN_RATIO:
        print("FAIL: 中文注释与独立说明性 docstring 行占比不足。", file=sys.stderr)
        return 1
    print("PASS: 中文注释检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
