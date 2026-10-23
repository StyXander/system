"""只对来源匹配且完成独立人工复核的封闭标签集计算指标；其余明确不计分。"""
from __future__ import annotations


def evaluate(payload: dict, packet: dict, pair_id: str, source_hashes: dict) -> dict:
    samples = [row for row in packet.get('samples', []) if row.get('pair_id') == pair_id]
    missing = {'status': 'not_completed', 'metrics': None,
               'reason': '没有覆盖全集且完成会计专业人工复核的来源一致标签'}
    if packet.get('status') != 'human_reviewed' or not packet.get('closed_world') or not samples:
        return missing
    if any(row.get('provenance') != 'human' or not row.get('reviewer') or row.get('source_hashes') != source_hashes
           or not isinstance(row.get('label'), bool) for row in samples):
        return missing
    ids = {row['event']['event_id'] for row in samples}
    predicted_events = {row['event_id'] for row in payload.get('events', [])}
    if predicted_events - ids:
        return {**missing, 'reason': '本臂发现了尚未人工标注的新事项，不能静默删去后评分'}
    truth_events = {row['event']['event_id'] for row in samples if row['label']}
    event_precision = len(predicted_events & truth_events) / len(predicted_events) if predicted_events else None
    metrics = {'event_extraction_precision': event_precision, 'event_extraction_recall':
        len(predicted_events & truth_events) / len(truth_events) if truth_events else None}
    actual_links = {f"{row['event_id']}|{row['financial_item_id']}|{(row.get('treatment_id') or '').split(':')[-1]}"
        for row in payload.get('relations', []) if row.get('grade') in {'A', 'B'}}
    if all(isinstance(row.get('relation_keys'), list) for row in samples):
        truth = {f"{row['event']['event_id']}|{key}" for row in samples for key in row['relation_keys']}
        tp, fp, fn = len(actual_links & truth), len(actual_links - truth), len(truth - actual_links)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        metrics.update(relation_precision=precision, relation_recall=recall,
            relation_f1=(2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None),
            false_association_rate=fp / len(actual_links) if actual_links else None)
    else:
        metrics.update(relation_precision=None, relation_recall=None, relation_f1=None, false_association_rate=None)
    rankings = {row['event_id']: row['pages'] for row in payload.get('retrieval', {}).get('rankings', [])}
    recalls = {5: [], 10: []}
    for row in samples:
        relevant = row.get('relevant_page_refs')
        if not isinstance(relevant, list) or not relevant:
            continue
        ranking = rankings.get(row['event']['event_id'], [])
        for k in recalls:
            recalls[k].append(len(set(ranking[:k]) & set(relevant)) / len(set(relevant)))
    metrics.update({f'note_recall_at_{k}': sum(values) / len(values) if values else None for k, values in recalls.items()})
    expected_rules = {row['event']['event_id']: row.get('correct_rule_ids') for row in samples}
    proposed = [(row['treatment_id'].split(':')[0], row['rule_id']) for row in payload.get('treatments', [])]
    scored = [(event, rule) for event, rule in proposed if isinstance(expected_rules.get(event), list)]
    metrics['accounting_candidate_path_precision'] = sum(rule in expected_rules[event] for event, rule in scored) / len(scored) if scored else None
    refs = [ref for row in payload.get('relations', []) for ref in row.get('supporting', []) + row.get('counter', [])]
    metrics['program_source_reference_validity'] = sum(bool(ref.get('verified')) for ref in refs) / len(refs) if refs else None
    abstention = [row for row in samples if row.get('should_abstain') is True]
    accepted_events = {row.split('|')[0] for row in actual_links}
    metrics['correct_abstention_rate'] = sum(row['event']['event_id'] not in accepted_events for row in abstention) / len(abstention) if abstention else None
    return {'status': 'human_labeled_partial_metrics' if any(value is None for value in metrics.values()) else 'human_labeled_metrics',
        'metrics': metrics, 'note': '附注Recall按登记文档页计算；候选会计路径与会计确认不同；引用有效率是程序来源校验，不是专家判断正确率。缺少标签的维度保持空值。'}
