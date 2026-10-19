"""盘点已有材料的可编辑文字，记录输入身份，不覆盖团队原件。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
rows = []
for path in args.directory.rglob('*'):
    if any(p in {'.git', '.venv', 'runtime', 'archive', 'node_modules', '.kilo'} for p in path.parts):
        continue
    if path.suffix not in {'.docx', '.pptx'} or path.name.startswith('~$'):
        continue
    if path.stat().st_size > 150*1024*1024:
        continue
    with zipfile.ZipFile(path) as package:
        parts = ['word/document.xml'] if path.suffix == '.docx' else sorted(
            [p for p in package.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml', p)],
            key=lambda n: int(re.search(r'(\d+)\.xml', n).group(1)))
        pages = []
        for part in parts:
            tree = ET.fromstring(package.read(part))
            texts = [element.text for element in tree.iter() if element.tag.endswith('}t') and element.text]
            pages.append({'part': part, 'texts': texts,
                          'images': sum(element.tag.endswith('}pic') for element in tree.iter())})
    rows.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'pages': pages})
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'files': len(rows), 'output': str(args.output)}, ensure_ascii=False))
