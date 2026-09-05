import json
from pathlib import Path


def test_contract_keeps_exact_laboratory_source_fields():
    contract = json.loads(Path("config/data_contract.json").read_text(encoding="utf-8"))
    assert [field["name"] for field in contract["fields"]] == [
        "id_venta",
        "fecha_venta",
        "producto",
        "categoria",
        "region",
        "cantidad",
        "precio_unitario",
    ]


def test_mandatory_olap_operators_are_versioned():
    olap = "\n".join(
        path.read_text(encoding="utf-8").upper()
        for path in sorted(Path("sql/olap").glob("*.sql"))
    )
    for operator in ("GROUP BY", "ROLLUP", "CUBE", "GROUPING SETS"):
        assert operator in olap


def test_star_schema_tables_are_versioned():
    ddl = Path("sql/redshift/02_create_tables.sql").read_text(encoding="utf-8").lower()
    for table in ("dim_fecha", "dim_producto", "dim_region", "fact_ventas"):
        assert f"dw.{table}" in ddl
