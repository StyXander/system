"""消融实验：九项条件校验与检索方式各自带来多少真实增量。

两条实验都只用可复现的确定性组件，不调用付费模型，不计算没有人工标签的准确率。

实验一（校验消融）：12 个对抗样本上比较
  V0 朴素匹配：只要财务项目存在且项目名出现，就当作“明确关联”。
  V1 九项条件：身份/期间/范围/性质/前提/证据/反证/勾稽逐项判定。
指标：错误A级数（把不应确认的关系判成A）、正确A级数。

实验二（检索消融）：真实五粮液报告对，看正确附注页是否进入候选前10。
  精确匹配 / 仅BM25 / 混合（BM25+精确+RRF）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.connectivity_extraction import load_registry, source_path  # noqa: E402
from backend.app.financial_impact import financial_linker  # noqa: E402
from backend.app.financial_impact import impact_verifier  # noqa: E402
from backend.app.financial_impact.models import AmountNature, RelationGrade, Stage  # noqa: E402
from backend.tests.test_financial_impact import SUPPORT, event, item, treatment  # noqa: E402

DECOYS = [
    ("期间错配", dict(event=dict(period="2025"), item=dict(period="2023"))),
    ("合并范围错配", dict(event=dict(scope="合并"), item=dict(scope="母公司"))),
    ("预算当投入", dict(event=dict(), item=dict(value_semantics=AmountNature.BUDGET, column_header="预算数"))),
    ("余额当投入", dict(event=dict(), item=dict(value_semantics=AmountNature.CLOSING_BALANCE, column_header="期末余额"))),
    ("研发投入当费用", dict(event=dict(amount_nature=AmountNature.INVESTMENT_INCURRED),
                        item=dict(value_semantics=AmountNature.EXPENSE))),
    ("另一个项目", dict(event=dict(), item=dict(row_header="污水处理厂项目", table_title="在建工程·污水处理厂"))),
    ("汇总行冒充", dict(event=dict(), item=dict(row_header="合计"))),
    ("缺金额", dict(event=dict(amounts=[], amount_nature=AmountNature.NONE), item=dict())),
    ("会计前提未验证", dict(event=dict(), item=dict(), treatment=dict(status="hypothesis"))),
    ("反证存在", dict(event=dict(), item=dict(), counter=[{"quote": "项目已终止", "pdf_page": 30}])),
    ("同名不同基地", dict(event=dict(subject="梅山基地"), item=dict(row_header="羧甲基纤维素改造项目"))),
    ("无事项目", dict(event=dict(), item=None)),
]


def naive_grade(case: dict) -> str:
    """V0：只按“有项目且有同名行”判断，不看期间、范围、金额性质与反证。"""
    if case.get("item") is None or case.get("counter"):
        return RelationGrade.C.value
    return RelationGrade.A.value


def run_verifier_ablation() -> dict:
    rows = []
    for label, patch in DECOYS:
        event_kwargs = dict(patch.get("event") or {})
        item_kwargs = dict(patch.get("item") or {}) if patch.get("item") is not None else None
        treatment_kwargs = dict(patch.get("treatment") or {})
        target_event = event(**event_kwargs)
        target_item = item(**item_kwargs) if item_kwargs is not None else None
        target_treatment = treatment(**treatment_kwargs) if treatment_kwargs else treatment()
        relation = impact_verifier.build_relation(
            target_event, target_item, target_treatment,
            support=SUPPORT, counter=patch.get("counter") or [])
        rows.append({"case": label, "naive": naive_grade(patch), "verified": relation.grade.value})
    legit = impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT)
    rows.append({"case": "正例：九项均成立", "naive": RelationGrade.A.value, "verified": legit.grade.value})
    naive_false_a = sum(1 for row in rows if row["case"] != "正例：九项均成立" and row["naive"] == "A")
    verified_false_a = sum(1 for row in rows if row["case"] != "正例：九项均成立" and row["verified"] == "A")
    return {
        "rows": rows,
        "naive_false_a": naive_false_a,
        "verified_false_a": verified_false_a,
        "correct_a_on_positive": legit.grade == RelationGrade.A,
        "note": "错误A级指把不应确认的关系判为明确关联；样本为受控对抗样本，不是企业真实总体。",
    }


def run_retrieval_ablation() -> dict:
    docs = [doc for doc in load_registry(ROOT) if doc.company == "五粮液" and doc.period == "2025"]
    if len(docs) < 2:
        return {"status": "unavailable", "reason": "五粮液双报告未登记"}
    from backend.app.financial_impact.engine import ESG_TERMS, _load_pages
    from backend.app.financial_impact.financial_notes import load_note_pages
    esg = next(doc for doc in docs if doc.report_type == "ESG")
    ar = next(doc for doc in docs if doc.report_type == "AR")
    esg_pages, _ = _load_pages(source_path(ROOT, esg), ESG_TERMS, max_pages=36)
    note_pages, _ = load_note_pages(source_path(ROOT, ar))
    index, _ = financial_linker.build_index({esg.document_id: esg_pages, ar.document_id: note_pages})
    target_event = event(project_name="成品酒包装及智能仓储配送一体化项目", aliases=[],
                         quote="配套建设成品酒包装及智能仓储配送一体化项目", pdf_page=19,
                         document_id=esg.document_id, stage=Stage.EXECUTING)
    target_treatment = treatment()
    target_page = 102
    lexical = index.search(financial_linker._query(target_event, [target_treatment]), limit=40)
    lexical_pages = [index.units[pos].page for pos, _ in lexical[:10]]
    exact = [(pos, 1.0) for pos, unit in enumerate(index.units)
             if "成品酒包装及智能仓储配送一体化项目" in unit.text][:20]
    exact_pages = [index.units[pos].page for pos, _ in exact[:10]]
    fused = financial_linker.rrf(lexical, exact)
    fused_pages = [index.units[pos].page for pos, _ in fused[:10]]
    return {
        "status": "ok", "target_page": target_page,
        "arms": {
            "exact": {"hit": target_page in exact_pages, "top_pages": exact_pages},
            "bm25": {"hit": target_page in lexical_pages, "top_pages": lexical_pages},
            "hybrid_rrf": {"hit": target_page in fused_pages, "top_pages": fused_pages},
        },
        "units": len(index.units),
        "note": "只检验正确附注页是否进入前10；检索命中不等于关联成立。",
    }


def main() -> int:
    payload = {"schema": "financial_ablation_v1",
               "verifier": run_verifier_ablation(),
               "retrieval": run_retrieval_ablation()}
    out = ROOT / "outputs/financial_ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    verifier = payload["verifier"]
    print(f"校验消融：朴素错误A {verifier['naive_false_a']} / 九项校验错误A {verifier['verified_false_a']}；"
          f"正例仍为A={verifier['correct_a_on_positive']}")
    for row in verifier["rows"]:
        print(f"  {row['case']:<16} 朴素={row['naive']:<4} 校验={row['verified']}")
    retrieval = payload["retrieval"]
    if retrieval.get("status") == "ok":
        for arm, detail in retrieval["arms"].items():
            print(f"检索 {arm:<10} 命中目标页={detail['hit']} top={detail['top_pages'][:6]}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
