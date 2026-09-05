"""Contract and business-rule validation for source sales."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from comercial_andina.source.catalog import Catalog


@dataclass(frozen=True)
class QualityIssue:
    """One failed rule for one source sale."""

    sale_id: str
    code: str
    message: str


def validate_rows(
    rows: Iterable[dict[str, Any]],
    catalog: Catalog,
    processing_date: date,
) -> list[QualityIssue]:
    """Evaluate required, type, catalog, consistency and duplicate rules."""

    issues: list[QualityIssue] = []
    seen_ids: set[str] = set()
    product_categories = catalog.product_categories

    for row in rows:
        sale_id = str(row.get("id_venta", "")).strip()
        if not sale_id:
            issues.append(QualityIssue(sale_id, "DQ-001", "id_venta is required"))
        elif sale_id in seen_ids:
            issues.append(QualityIssue(sale_id, "DQ-002", "id_venta is duplicated"))
        seen_ids.add(sale_id)

        sale_date = _as_date(row.get("fecha_venta"))
        if sale_date is None or sale_date > processing_date:
            issues.append(QualityIssue(sale_id, "DQ-003", "fecha_venta is invalid or future"))

        product = str(row.get("producto", "")).strip()
        category = str(row.get("categoria", "")).strip()
        region = str(row.get("region", "")).strip()
        if not product or not category or not region:
            issues.append(QualityIssue(sale_id, "DQ-004", "business attributes are required"))

        quantity = _as_decimal(row.get("cantidad"))
        if quantity is None or quantity <= 0 or quantity != quantity.to_integral_value():
            issues.append(QualityIssue(sale_id, "DQ-005", "cantidad must be a positive integer"))

        price = _as_decimal(row.get("precio_unitario"))
        if price is None or price <= 0:
            issues.append(QualityIssue(sale_id, "DQ-006", "precio_unitario must be positive"))

        if product and product not in product_categories:
            issues.append(QualityIssue(sale_id, "DQ-007", "producto is not recognized"))
        if region and region not in catalog.regions:
            issues.append(QualityIssue(sale_id, "DQ-007", "region is not recognized"))
        if category and category not in catalog.categories:
            issues.append(QualityIssue(sale_id, "DQ-007", "categoria is not recognized"))
        if product in product_categories and product_categories[product] != category:
            issues.append(
                QualityIssue(sale_id, "DQ-008", "producto and categoria are inconsistent")
            )

    return issues


def _as_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
