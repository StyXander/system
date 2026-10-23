"""来源二完整对抗集纳入发布回归；保留原始样本和预期。"""
import pytest
from tools.hardening.adversarial_suite import SAMPLES, evaluate


@pytest.mark.parametrize("sample", SAMPLES, ids=[item["id"] for item in SAMPLES])
def test_source_two_adversarial(sample):
    result = evaluate(sample)
    assert result["pass"], result
