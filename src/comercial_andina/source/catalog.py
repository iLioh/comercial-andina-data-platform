"""Catalog loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Product:
    """Product master-data entry used by the synthetic source."""

    name: str
    category: str
    min_price: Decimal
    max_price: Decimal


@dataclass(frozen=True)
class Catalog:
    """Validated product and regional reference data."""

    regions: tuple[str, ...]
    products: tuple[Product, ...]

    @property
    def categories(self) -> frozenset[str]:
        return frozenset(product.category for product in self.products)

    @property
    def product_categories(self) -> dict[str, str]:
        return {product.name: product.category for product in self.products}


def load_catalog(path: str | Path) -> Catalog:
    """Load the repository catalog and enforce the agreed cardinalities."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    regions = tuple(payload["regions"])
    products = tuple(
        Product(
            name=item["name"],
            category=item["category"],
            min_price=Decimal(str(item["min_price"])),
            max_price=Decimal(str(item["max_price"])),
        )
        for item in payload["products"]
    )

    if len(regions) != 5 or len(set(regions)) != 5:
        raise ValueError("The catalog must contain exactly five unique regions")
    if len(products) != 20 or len({product.name for product in products}) != 20:
        raise ValueError("The catalog must contain exactly twenty unique products")
    if len({product.category for product in products}) != 5:
        raise ValueError("The catalog must contain exactly five categories")
    if any(product.min_price <= 0 or product.max_price < product.min_price for product in products):
        raise ValueError("Every product must have a valid positive price range")

    return Catalog(regions=regions, products=products)
