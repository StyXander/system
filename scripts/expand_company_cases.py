"""有界官方案例接入；按真实原件逐家记录，不把候选数量当成完成数量。"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.connectivity_onboarding import discover_pair, prepare_pair
from backend.app.connectivity_catalog import list_pairs, export_snapshot

CANDIDATES = [
    ('601899', '紫金矿业', '有色金属采矿'), ('600585', '海螺水泥', '建材'),
    ('601012', '隆基绿能', '新能源'), ('002594', '比亚迪', '汽车'),
    ('601088', '中国神华', '能源'), ('600875', '东方电气', '机械制造'),
    ('600031', '三一重工', '机械制造'), ('600887', '伊利股份', '食品饮料'),
    ('000651', '格力电器', '家电制造'), ('600690', '海尔智家', '家电制造'),
    ('601766', '中国中车', '装备制造'), ('600028', '中国石化', '能源化工'),
    ('600309', '万华化学', '化工'), ('600900', '长江电力', '能源'),
    ('600036', '招商银行', '金融'), ('601668', '中国建筑', '建筑'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2025)
    parser.add_argument('--tickers', default='')
    parser.add_argument('--output', default='outputs/enterprise-expansion')
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    selected = [r for r in CANDIDATES if not args.tickers or r[0] in args.tickers.split(',')]
    results = []
    from backend.app.company_discovery import directory
    directory(ROOT)  # 冷启动先准备一次身份目录，避免并发刷新导致候选被误记失败。

    def work(candidate):
        ticker, company, industry = candidate
        record = {'ticker': ticker, 'company': company, 'industry': industry, 'year': args.year, 'model_status': 'not_run'}
        try:
            found = discover_pair(ROOT, ticker, args.year)
            (out / f'{ticker}-discovery.json').write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding='utf-8')
            record.update(discovery_state=found['state'], missing=found['missing'])
            if found['state'] == 'paired':
                pair = prepare_pair(ROOT, found, industry=industry)
                record.update(state='verified', pair_id=pair['pair_id'], documents=pair['documents'], inspection=pair['inspection'])
            else:
                record['state'] = found['state']
        except Exception as error:
            record.update(state='failed', error=f'{type(error).__name__}: {str(error)[:500]}')
        return record

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(work, row): row for row in selected}
        for future in as_completed(futures):
            record = future.result()
            results.append(record)
            print(record['ticker'], record['company'], record['state'], record.get('error', ''), flush=True)
            (out / 'acquisition.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    # 快照由验证后的持久目录导出，不人工手写企业或预期数据。
    records, persistence = list_pairs(ROOT, refresh=True)
    export_snapshot(ROOT, records, persistence)
    print(json.dumps({'candidates': len(selected), 'verified_pairs': len(records), 'persistence': persistence}, ensure_ascii=False))


if __name__ == '__main__':
    main()
