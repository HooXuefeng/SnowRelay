from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

SCHEMA = "snowedge-import/1"


def _text(value: object, limit: int = 12000) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()[:limit]


def _input_manifest(paths: Iterable[str]) -> list[dict]:
    manifest = []
    for raw_path in paths:
        path = Path(raw_path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append({"name": path.name, "sha256": digest.hexdigest(), "size": path.stat().st_size})
    return manifest


def _without_known_password(value: object, password: str, limit: int = 12000) -> str:
    text = _text(value, limit)
    if password:
        text = text.replace(password, "••••")
    return text


def build_snowedge_package(df: pd.DataFrame, input_files: Iterable[str]) -> dict:
    records = []
    for _, row in df.iterrows():
        password = _text(row.get("password"), 1000)
        records.append({
            "asset": _text(row.get("asset_ip"), 500) or _text(row.get("target_url"), 2000) or _text(row.get("hostname"), 500),
            "hostname": _text(row.get("hostname"), 500),
            "url": _text(row.get("target_url"), 2000),
            "port": _text(row.get("port"), 8),
            "protocol": _text(row.get("protocol"), 20).lower() or "tcp",
            "service": _text(row.get("service"), 100),
            "severity": _text(row.get("severity"), 30),
            "cvss": _text(row.get("cvss"), 16),
            "title": _text(row.get("vuln_name"), 300),
            "cve": _text(row.get("cve"), 200),
            "description": _without_known_password(row.get("description"), password),
            "evidence": _without_known_password(row.get("evidence"), password),
            "recommendation": _without_known_password(row.get("solution"), password, 8000),
            "username": _text(row.get("username"), 200),
            "credential_status": _text(row.get("credential_status"), 80),
            "risk_type": _text(row.get("risk_type"), 160),
            "match_reason": _without_known_password(row.get("match_reason"), password, 1000),
            "is_high_vulnerability": _text(row.get("is_high_vulnerability"), 8),
            "is_high_risk_port": _text(row.get("is_high_risk_port"), 8),
            "is_weak_password": _text(row.get("is_weak_password"), 8),
            "source": {
                "category": _text(row.get("source_category"), 80),
                "platform": _text(row.get("source_platform"), 120),
                "file": _text(row.get("source_file"), 300),
                "sheet": _text(row.get("source_sheet"), 200),
                "row": _text(row.get("original_row"), 20),
            },
        })
    return {
        "schema": SCHEMA,
        "producer": {"name": "SnowRelay", "version": "0.5.0"},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": _input_manifest(input_files),
        "record_count": len(records),
        "sensitive_fields": {"password_included": False},
        "records": records,
    }


def export_snowedge_package(df: pd.DataFrame, output_path: str, input_files: Iterable[str]) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    package = build_snowedge_package(df, input_files)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.stem}-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(package, handle, ensure_ascii=False, indent=2)
        os.replace(temp_name, output)
    finally:
        Path(temp_name).unlink(missing_ok=True)
