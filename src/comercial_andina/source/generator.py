"""Deterministic generator for the simulated OLTP sales source."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from comercial_andina.source.catalog import Catalog

SOURCE_COLUMNS = (
    "id_venta",
    "fecha_venta",
    "producto",
    "categoria",
    "region",
    "cantidad",
    "precio_unitario",
)

DEFAULT_SEED = 20260905
DEFAULT_PROCESSING_DATE = date(2026, 9, 1)
DEFAULT_START_DATE = date(2023, 9, 1)
CONTROLLED_INVALID_COUNT = 20


def generate_sales(
    catalog: Catalog,
    record_count: int = 10_000,
    seed: int = DEFAULT_SEED,
    processing_date: date = DEFAULT_PROCESSING_DATE,
) -> list[dict[str, Any]]:
    """Generate repeatable sales and inject twenty traceable quality failures."""

    if record_count < CONTROLLED_INVALID_COUNT:
        raise ValueError(f"record_count must be at least {CONTROLLED_INVALID_COUNT}")

    randomizer = random.Random(seed)
    available_days = (processing_date - DEFAULT_START_DATE).days
    region_weights = (45, 17, 15, 13, 10)
    rows: list[dict[str, Any]] = []

    for sale_id in range(1, record_count + 1):
        product = randomizer.choice(catalog.products)
        price_in_cents = randomizer.randint(
            int(product.min_price * 100),
            int(product.max_price * 100),
        )
        rows.append(
            {
                "id_venta": sale_id,
                "fecha_venta": DEFAULT_START_DATE
                + timedelta(days=randomizer.randint(0, available_days)),
                "producto": product.name,
                "categoria": product.category,
                "region": randomizer.choices(catalog.regions, weights=region_weights, k=1)[0],
                "cantidad": randomizer.choices((1, 2, 3, 4, 5), weights=(46, 27, 15, 8, 4), k=1)[0],
                "precio_unitario": Decimal(price_in_cents) / Decimal(100),
            }
        )

    _inject_controlled_errors(rows, processing_date)
    return rows


def _inject_controlled_errors(rows: list[dict[str, Any]], processing_date: date) -> None:
    """Inject known failures in the final twenty rows for demonstrable DQ evidence."""

    invalid_rows = rows[-CONTROLLED_INVALID_COUNT:]
    for row in invalid_rows[0:4]:
        row["cantidad"] = 0
    for row in invalid_rows[4:8]:
        row["precio_unitario"] = Decimal("0.00")
    for row in invalid_rows[8:11]:
        row["producto"] = ""
    for row in invalid_rows[11:14]:
        row["region"] = "REGION_NO_RECONOCIDA"
    for row in invalid_rows[14:17]:
        row["categoria"] = "CATEGORIA_INCONSISTENTE"
    for offset, row in enumerate(invalid_rows[17:20], start=1):
        row["fecha_venta"] = processing_date + timedelta(days=offset)


def write_sales_csv(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    """Write the exact seven-column source contract to a UTF-8 CSV file."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "fecha_venta": row["fecha_venta"].isoformat(),
                    "precio_unitario": f'{row["precio_unitario"]:.2f}',
                }
            )
    return destination
