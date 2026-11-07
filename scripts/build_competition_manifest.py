"""Build reproducible release metadata without reading credentials or inventing results."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset-version', required=True)
    parser.add_argument('--model', default='not_run')
    args = parser.parse_args()
    paths = ['index.html', 'assets/official-v4/evidence-studio.css',
             'backend/app/connectivity_matter_rules.json', 'docs/competition/EXPERIMENT_PROTOCOL.md']
    manifest = {'code_sha': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                'working_tree_dirty': bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
                'dataset_version': args.dataset_version, 'model': args.model,
                'professional_evaluation': 'not_run', 'files': {}}
    for name in paths:
        manifest['files'][name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
