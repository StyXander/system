"""六项规则卡的程序入口：规范提供方向，企业原文证明本次关系。

这里只登记通用角色与前提，不存公司金额、页码或参考答案。
研发与环保共用组成算子，避免为每个场景另造计算引擎。
"""
RULES = {
    "EQ-001": {"name": "同口径数值", "operator": "equal", "roles": ["left", "right"], "basis": ["CN01", "CN03", "CN04", "CN07"]},
    "RD-001": {"name": "研发投入组成", "operator": "sum", "roles": ["total", "component"], "basis": ["CN03", "CN04", "CN07"]},
    "ENV-001": {"name": "环保投入组成", "operator": "sum", "roles": ["total", "component"], "basis": ["CN03", "CN04", "CN07"]},
    "INT-001": {"name": "比例与强度分母", "operator": "ratio", "roles": ["numerator", "denominator", "reported_ratio"], "basis": ["CN07"]},
    "OCC-001": {"name": "多位置关联", "operator": "occurrences", "roles": ["occurrence"], "basis": ["CN01", "CN03", "CN06", "CN08"]},
    "NAR-001": {"name": "叙述解释与依据", "operator": "narrative", "roles": ["occurrence"], "basis": ["CN03", "CN05", "CN06", "CN08", "AS02", "AS04"]},
}
BASE_CONDITIONS = ("主体", "期间", "定义", "范围", "单位")
TOPICS = {
    "research": {"name": "研发投入", "keywords": ["研发投入", "研发支出", "研发费用", "研究开发", "资本化研发", "费用化研发", "新产品研发试制费", "研发人员"]},
    "environment": {"name": "环保投入", "keywords": ["环保投入", "环境保护投入", "环境保护相关资金", "环保资金", "环保投资", "环保费用", "环境治理", "环保资本化", "环保费用化"]},
    "intensity": {"name": "强度与分母", "keywords": ["耗水", "用水强度", "取水强度", "年度总用水", "总取水量", "温室气体排放总量", "排放强度", "能源强度", "能源使用强度", "能耗强度", "综合能源消耗", "能源消耗量", "粗钢产量", "营业收入", "营业总收入", "主营业务收入", "研发投入占"]},
}


def required_conditions(operator: str) -> tuple[str, ...]:
    """组成关系还须证明覆盖完整且互不重复，比例须确认公式。"""
    extra = {"sum": ("组成完整", "互不重叠"), "ratio": ("公式",)}
    return BASE_CONDITIONS + extra.get(operator, ())
