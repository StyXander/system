"""Office COM不可用时的真实替代预览；不冒充原生PowerPoint验收。"""
from pathlib import Path
import subprocess
import os
import json
import uuid
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'outputs/ai4/materials'
converter = Path('C:/Program Files/LibreOffice/program/soffice.com')
reports = []
for source in sorted(base.glob('*')):
    if source.suffix not in {'.docx', '.pptx'}:
        continue
    destination = base / ('word-preview' if source.suffix == '.docx' else 'ppt-preview')
    destination.mkdir(parents=True, exist_ok=True)
    profile = ROOT / 'runtime' / ('lo-' + source.suffix[1:] + '-' + uuid.uuid4().hex[:8])
    subprocess.run([str(converter), '-env:UserInstallation=' + profile.as_uri(), '--headless',
                    '--convert-to', 'pdf', '--outdir', str(destination), str(source)],
                   check=True, timeout=180,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    pdf = destination / (source.stem + '.pdf')
    page_paths = []
    with pymupdf.open(pdf) as document:
        for index, page in enumerate(document):
            image = destination / f'page-{index + 1}.png'
            page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), alpha=False).save(image)
            page_paths.append(image)
        reports.append({'source': source.name, 'renderer': 'LibreOffice+PyMuPDF', 'pages': len(document),
                        'native_office': 'not_verified', 'visual_inspection': 'pending'})
    for start in range(0, len(page_paths), 8):
        contact = pymupdf.open()
        sheet = contact.new_page(width=1960, height=1320)
        for index, path in enumerate(page_paths[start:start + 8]):
            x, y = (index % 4)*490, (index // 4)*660
            sheet.insert_text((x+10, y+20), f'Page {start+index+1}', fontsize=14)
            sheet.insert_image(pymupdf.Rect(x+10, y+30, x+480, y+650), filename=str(path), keep_proportion=True)
        sheet.get_pixmap(alpha=False).save(destination / f'contact-{start//8+1}.png')
        contact.close()
(base / 'preview-report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(reports, ensure_ascii=False))
