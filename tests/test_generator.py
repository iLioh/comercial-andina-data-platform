import csv
from datetime import date

from comercial_andina.quality.validator import validate_rows
from comercial_andina.source.catalog import load_catalog
from comercial_andina.source.generator import generate_sales, write_sales_csv
from comercial_andina.source.manifest import build_manifest


def test_generator_matches_scope_and_controlled_failures(tmp_path):
    catalog = load_catalog("config/catalogs.json")
    rows = generate_sales(catalog, record_count=10_000)
    issues = validate_rows(rows, catalog, date(2026, 9, 1))

    assert len(rows) == 10_000
    assert len(catalog.products) == 20
    assert len(catalog.categories) == 5
    assert len(catalog.regions) == 5
    assert len({issue.sale_id for issue in issues}) == 20
    assert len(rows) - len({issue.sale_id for issue in issues}) == 9_980

    csv_path = write_sales_csv(rows, tmp_path / "ventas.csv")
    with csv_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        assert reader.fieldnames == [
            "id_venta",
            "fecha_venta",
            "producto",
            "categoria",
            "region",
            "cantidad",
            "precio_unitario",
        ]

    manifest = build_manifest(csv_path, "BATCH-TEST-001")
    assert manifest["record_count"] == 10_000
    assert len(manifest["sha256"]) == 64


def test_generator_is_deterministic():
    catalog = load_catalog("config/catalogs.json")
    assert generate_sales(catalog, record_count=100) == generate_sales(
        catalog, record_count=100
    )
