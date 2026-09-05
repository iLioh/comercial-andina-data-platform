"""Batch manifest generation for RAW traceability and reconciliation."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    """Calculate a SHA-256 digest without loading the whole file into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    csv_path: str | Path,
    batch_id: str,
    schema_version: str = "1.0",
    source_system: str = "VENTAS_OLTP",
) -> dict[str, Any]:
    """Build counts, amount and integrity metadata for an extracted batch."""

    source_path = Path(csv_path)
    count = 0
    total_amount = Decimal("0.00")
    with source_path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            count += 1
            try:
                total_amount += Decimal(row["cantidad"]) * Decimal(row["precio_unitario"])
            except (InvalidOperation, TypeError, ValueError):
                continue

    return {
        "batch_id": batch_id,
        "source_system": source_system,
        "schema_version": schema_version,
        "extracted_at_utc": datetime.now(UTC).isoformat(),
        "file_name": source_path.name,
        "record_count": count,
        "total_amount": f"{total_amount:.2f}",
        "sha256": sha256_file(source_path),
    }


def write_manifest(manifest: dict[str, Any], output_path: str | Path) -> Path:
    """Persist a manifest as deterministic, human-readable JSON."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
