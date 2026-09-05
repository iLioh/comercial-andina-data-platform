from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from comercial_andina.etl import pipeline
from comercial_andina.etl.pipeline import create_batch_id, run_daily_pipeline


def test_batch_id_uses_business_time():
    current = datetime(2026, 9, 5, 7, 30, 45, tzinfo=ZoneInfo("America/Lima"))
    assert create_batch_id(current) == "BATCH-20260905-073045"


def test_pipeline_rejects_unsafe_batch_before_external_calls():
    with pytest.raises(ValueError, match="unsupported"):
        run_daily_pipeline(object(), "BATCH'; DROP TABLE dw.fact_ventas;--")


def test_reconciliation_accepts_balanced_batch(monkeypatch):
    class Executor:
        def query_one(self, _sql):
            return {
                "registros_origen": 10_000,
                "registros_validos": 9_980,
                "registros_rechazados": 20,
                "registros_publicados": 9_980,
                "importe_publicado": "25922873.61",
                "estado": "SUCCESS",
            }

    monkeypatch.setattr(pipeline, "_redshift_executor", lambda _settings: Executor())
    result = pipeline.reconcile_batch(object(), "BATCH-20260905-001", 10_000)

    assert result["valid_count"] == 9_980
    assert result["rejected_count"] == 20
    assert result["status"] == "SUCCESS"


def test_reconciliation_fails_when_valid_rows_are_not_published(monkeypatch):
    class Executor:
        def query_one(self, _sql):
            return {
                "registros_origen": 100,
                "registros_validos": 99,
                "registros_rechazados": 1,
                "registros_publicados": 98,
                "importe_publicado": "1000.00",
                "estado": "FAILED",
            }

    monkeypatch.setattr(pipeline, "_redshift_executor", lambda _settings: Executor())
    with pytest.raises(RuntimeError, match="Warehouse reconciliation failed"):
        pipeline.reconcile_batch(object(), "BATCH-20260905-002", 100)
