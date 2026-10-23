"""超限用量不能从账本消失，批量入口不能绕过已消费token。"""
import pytest
from backend.app.public_model import PublicModelLedger, PublicModelQuotaError, QuotaConfig


def test_exceeded_consumption_is_saved_and_blocks_both_admission_paths(tmp_path):
    ledger = PublicModelLedger(tmp_path, config=QuotaConfig(daily_input_tokens=10))
    reservation = ledger.reserve_batch('test')
    with pytest.raises(PublicModelQuotaError, match='输入'):
        ledger.settle(reservation, input_tokens=11, output_tokens=2)
    with ledger._connect() as db:
        row = db.execute('select input_tokens,output_tokens,released,settled from model_usage').fetchone()
        assert tuple(row) == (11, 2, 0, 1)
    for reserve in (lambda: ledger.reserve_batch('next'), lambda: ledger.reserve('next')):
        with pytest.raises(PublicModelQuotaError, match='token'):
            reserve()
