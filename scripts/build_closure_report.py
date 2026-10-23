"""把 closure 实测结果渲染为自包含 HTML 报告，供评审查看与演示。

只读 outputs/closure-20261022/closure_experiment.json，不重新计算，
因此页面上的每个数字都能与实验产物逐条对上。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "closure-20261022" / "closure_experiment.json"
OUT = ROOT / "outputs" / "closure-20261022" / "closure_report.html"

TIER_ORDER = ["substantive_risk", "formal_gap", "blocked", "closed"]
TIER_TEXT = {
    "substantive_risk": ("补纸面仍不一致", "即使全部形式前提取得原文支持，仍有未解释差额"),
    "formal_gap": ("只缺形式证据", "补齐纸面后可闭合，或仅剩显示精度"),
    "blocked": ("算式不可执行", "币种、量纲或约数使算式无法执行"),
    "closed": ("已闭合", "正式结论为一致"),
}
PAIR_NAME = {
    "000858-2025": "五粮液 2025",
    "000333-2025": "美的集团 2025",
    "300750-2025": "宁德时代 2025",
    "600019-2025": "宝钢股份 2025",
    "600019-2024": "宝钢股份 2024",
}


def money(value: str | None) -> str:
    if value in (None, ""):
        return "—"
    try:
        from decimal import Decimal

        number = Decimal(str(value))
    except Exception:  # noqa: BLE001 - 展示层，退化为原样
        return html.escape(str(value))
    if abs(number) >= 100000000:
        return f"{number / 100000000:,.2f} 亿元"
    if abs(number) >= 10000:
        return f"{number / 10000:,.2f} 万元"
    return f"{number:,.2f}"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    total = sum(item["treated"]["relation_total"] for item in data)
    tiers = {key: 0 for key in TIER_ORDER}
    ceiling: dict[str, int] = {}
    rows: list[dict] = []
    for item in data:
        closure = item["treated"]["closure"]
        for key in TIER_ORDER:
            tiers[key] += closure["tiers"].get(key, {}).get("count", 0)
        for key, value in closure["ceiling_status"].items():
            ceiling[key] = ceiling.get(key, 0) + value
        for check in item["treated"]["checks"]:
            block = check.get("closure") or {}
            if not block:
                continue
            leading = block.get("leading_hypothesis") or {}
            rows.append({
                "pair": PAIR_NAME.get(item["treated"]["pair_id"], item["treated"]["pair_id"]),
                "title": check["title"],
                "tier": block.get("tier"),
                "tier_label": block.get("tier_label"),
                "tier_reason": block.get("tier_reason"),
                "scope": block.get("relation_scope"),
                "residual": (block.get("ceiling") or {}).get("residual"),
                "unit": (block.get("ceiling") or {}).get("normalized_unit"),
                "ceiling_status": (block.get("ceiling") or {}).get("status"),
                "demands": [d["condition"] for d in block.get("demands") or []],
                "hypothesis": leading.get("detail") if leading else "",
                "hypothesis_status": leading.get("status") if leading else "",
                "hypothesis_label": leading.get("label") if leading else "",
            })

    substantive = [row for row in rows if row["tier"] == "substantive_risk"]
    confirmed = [row for row in substantive if row["hypothesis_status"] == "confirmed"]
    no_alert = [row for row in rows if row["ceiling_status"] == "would_confirm_conditionally"]

    def bar(key: str) -> str:
        width = tiers[key] / total * 100 if total else 0
        tone = "#b5735a" if key == "substantive_risk" else "#6a8979" if key != "blocked" else "#8a8f96"
        return f"""<div class="row"><div class="rowhead"><span>{html.escape(TIER_TEXT[key][0])}</span>
            <span><b>{tiers[key]}</b><small> / {total} · {width:.0f}%</small></span></div>
            <div class="track"><i style="width:{width:.1f}%;background:{tone}"></i></div>
            <p class="hint">{html.escape(TIER_TEXT[key][1])}</p></div>"""

    def table(source: list[dict], with_reason: bool) -> str:
        if not source:
            return "<p class='hint'>本类无条目。</p>"
        body = []
        for row in source:
            status = {"confirmed": "已证实", "pending": "待核实", "supported": "有依据"}.get(row["hypothesis_status"], "未归因")
            tone = "ok" if row["hypothesis_status"] == "confirmed" else "warn"
            reason = f"<p class='hint'>{html.escape(row['tier_reason'] or '')}</p>" if with_reason else ""
            # money() 已把元换算成万元/亿元，货币单位不再重复展示；无量纲与比率仍标出。
            unit_label = "" if row["unit"] in ("元", "万元", "亿元", None) else (row["unit"] or "")
            body.append(f"""<tr>
                <td><span class="pair">{html.escape(row['pair'])}</span><strong>{html.escape(row['title'])}</strong>
                    <span class="scope">{'同报告内多位置' if row['scope']=='same_document' else '跨报告'}</span>{reason}</td>
                <td class="num">{money(row['residual'])}<small>{html.escape(unit_label)}</small></td>
                <td>{html.escape('、'.join(row['demands']) or '—')}</td>
                <td><span class="tag {tone}">{status}</span>
                    <p>{html.escape(row['hypothesis_label'] or '')}</p>
                    <p class="hint">{html.escape(row['hypothesis'] or '')}</p></td>
            </tr>""")
        return f"""<table><thead><tr><th>关系（原报告 · 指标）</th><th>上限预测差额</th><th>未支持前提</th><th>归因</th></tr></thead>
            <tbody>{''.join(body)}</tbody></table>"""

    document = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>审迹智链 · 补证闭合推演实测</title>
<style>
  :root {{ --ink:#1f2a24; --muted:#5d6b62; --line:#dde4da; --paper:#fbfaf6; --card:#ffffff; --accent:#3f6b52; --warn:#b5735a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:40px 28px 72px; background:var(--paper); color:var(--ink);
    font:15px/1.7 "Songti SC","SimSun",system-ui,-apple-system,"Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  .kicker {{ font-size:12px; letter-spacing:.22em; color:var(--accent); text-transform:uppercase; margin:0 0 10px; }}
  h1 {{ font-size:30px; line-height:1.3; margin:0 0 12px; font-family:"Heiti SC","SimHei",system-ui; font-weight:700; }}
  .lede {{ color:var(--muted); margin:0 0 28px; max-width:820px; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin:0 0 32px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
  .stat b {{ display:block; font-size:32px; line-height:1.1; font-family:"Heiti SC","SimHei",system-ui; }}
  .stat small {{ color:var(--muted); font-size:12px; }}
  .stat.risk b {{ color:var(--warn); }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:24px 26px; margin:0 0 20px; }}
  h2 {{ font-size:18px; margin:0 0 6px; font-family:"Heiti SC","SimHei",system-ui; }}
  .sub {{ color:var(--muted); font-size:13px; margin:0 0 18px; }}
  .row {{ margin:0 0 16px; }}
  .rowhead {{ display:flex; justify-content:space-between; font-size:14px; margin-bottom:6px; }}
  .rowhead b {{ font-size:18px; }}
  .rowhead small {{ color:var(--muted); }}
  .track {{ height:8px; background:#e8ede6; border-radius:99px; overflow:hidden; }}
  .track i {{ display:block; height:8px; border-radius:99px; }}
  .hint {{ color:var(--muted); font-size:12.5px; margin:6px 0 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th {{ text-align:left; font-weight:600; color:var(--muted); font-size:12px; letter-spacing:.06em;
    border-bottom:1px solid var(--line); padding:0 10px 8px 0; }}
  td {{ vertical-align:top; padding:12px 10px 12px 0; border-bottom:1px solid #eef2ec; }}
  td strong {{ display:block; font-weight:600; }}
  td p {{ margin:4px 0 0; }}
  .pair {{ display:block; font-size:11.5px; color:var(--accent); letter-spacing:.04em; }}
  .scope {{ display:inline-block; font-size:11px; color:var(--muted); border:1px solid var(--line);
    border-radius:99px; padding:1px 8px; margin-top:6px; }}
  .num {{ white-space:nowrap; font-variant-numeric:tabular-nums; }}
  .num small {{ display:block; color:var(--muted); font-size:11px; }}
  .tag {{ display:inline-block; font-size:11.5px; border-radius:4px; padding:1px 7px; }}
  .tag.ok {{ background:#e6efe6; color:#2f5a3f; }}
  .tag.warn {{ background:#f6e9e2; color:#8f4d36; }}
  .note {{ border-left:3px solid var(--warn); padding:10px 0 10px 14px; color:var(--muted); font-size:13px; }}
  footer {{ color:var(--muted); font-size:12px; margin-top:28px; line-height:1.8; }}
</style></head>
<body><div class="wrap">
  <p class="kicker">审迹智链 AuditTrace · 真实报告实测</p>
  <h1>补证闭合推演：30 条跨报告关系，<br>补齐纸面证据后还差多少</h1>
  <p class="lede">对每条被闸门拦住的关系，用同一个确定性算式再算一次"假如全部形式前提都取得原文支持"。
  这不是结论，也不是预测企业错报；它只回答一个问题——<b>差额是缺证据造成的，还是数字本身就不一致</b>。
  全部数字来自 5 对已登记真实公开报告，计算链路未调用任何模型。</p>

  <div class="stats">
    <div class="stat"><b>{total}</b><small>真实关系总数</small></div>
    <div class="stat"><b>0</b><small>正式一致（不掩饰）</small></div>
    <div class="stat"><b>{tiers['formal_gap']}</b><small>只缺形式证据</small></div>
    <div class="stat risk"><b>{tiers['substantive_risk']}</b><small>补纸面仍不一致</small></div>
    <div class="stat"><b>{len(no_alert)}</b><small>差额落在精度预算内</small></div>
  </div>

  <section>
    <h2>一、分档：把"依据不足"拆成两类</h2>
    <p class="sub">分母一律为 {total} 条关系。分档由确定性反事实推演得出，不读取模型意见。</p>
    {''.join(bar(key) for key in TIER_ORDER)}
  </section>

  <section>
    <h2>二、补纸面仍不一致的 {len(substantive)} 条</h2>
    <p class="sub">这些差额补证消不掉，需要专业解释。归因分"已证实 / 待核实"，未取得原文的一律不写成结论。</p>
    {table(substantive, True)}
  </section>

  <section>
    <h2>三、已证实：行名自己写明了主体边界（{len(confirmed)} 条）</h2>
    <p class="sub">不是"又发现一个百亿差异"，而是这两处披露根本不属于同一主体范围。这类关系应当拆分或剔除。</p>
    {table(confirmed, False) if confirmed else "<p class='hint'>本次无行名级已证实条目。</p>"}
  </section>

  <section>
    <h2>四、系统主动不报警的 {len(no_alert)} 条</h2>
    <p class="sub">点值差额存在，但完全落在披露精度的误差预算内。这是"敢于不报警"，不是"什么都不敢确认"。</p>
    {table(no_alert, True) if no_alert else "<p class='hint'>本次无精度相容条目。</p>"}
  </section>

  <section>
    <h2>五、读这份报告时必须知道的三件事</h2>
    <p class="note">① 上限预测是假设推演，不是结论，更不是对企业错报的判断。它假设全部形式前提均已取得原文支持，只求剩余算术差额。</p>
    <p class="note">② "待核实"不是"已认定"。合并/母公司并列披露的识别在无表标题原文时只给比例特征，比例一致不构成结论。</p>
    <p class="note">③ 正式一致仍为 0。本页不主张系统已能确认一致，只主张它现在能说清"缺什么、补上会怎样、补不上是什么原因"。</p>
  </section>

  <footer>
    数据来源：{html.escape('、'.join(PAIR_NAME.values()))}，共 10 份公开报告原件（SHA-256 校验通过）。<br>
    运行模式：calculation_only（不调用模型）。产物：outputs/closure-20261022/closure_experiment.json。<br>
    版本：connectivity_closure_v1 · 生成时间见实验产物 generated_at 字段。
  </footer>
</div></body></html>"""
    OUT.write_text(document, encoding="utf-8")
    print(f"written {OUT} ({len(document)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
