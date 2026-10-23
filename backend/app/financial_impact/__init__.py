"""财务穿透分析层。

对外只暴露两类入口：
- build / for_pair：一次完整运行，返回可序列化结果。
- 各子模块：事项抽取、附注解析、会计映射、混合检索、图谱、裁决、影响分析，可单独测试。

边界：本包不修改正式核验结论，不写回六类规则状态，不替企业认定披露是否属实。
"""
from .engine import ENGINE_VERSION, build, for_pair
from .models import (AccountingRule, AccountingTreatment, AmountNature, ConditionCheck, FinancialImpactResult,
                     FinancialItem, ImpactRelation, RelationGrade, Stage, SustainabilityEvent)

__all__ = [
    "build", "for_pair", "ENGINE_VERSION",
    "FinancialImpactResult", "SustainabilityEvent", "FinancialItem", "AccountingRule",
    "AccountingTreatment", "ImpactRelation", "ConditionCheck", "RelationGrade", "Stage", "AmountNature",
]
