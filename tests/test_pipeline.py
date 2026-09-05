from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from comercial_andina.etl.pipeline import create_batch_id, run_daily_pipeline


def test_batch_id_uses_business_time():
    current = datetime(2026, 9, 5, 7, 30, 45, tzinfo=ZoneInfo("America/Lima"))
    assert create_batch_id(current) == "BATCH-20260905-073045"


def test_pipeline_rejects_unsafe_batch_before_external_calls():
    with pytest.raises(ValueError, match="unsupported"):
        run_daily_pipeline(object(), "BATCH'; DROP TABLE dw.fact_ventas;--")
