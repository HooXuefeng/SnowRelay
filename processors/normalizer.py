from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

import pandas as pd

from adapters.field_mapper import build_mapping, detect_platform, detect_source_category
from models.schema import STANDARD_COLUMNS

SEVERITY_MAP = {
    "critical": "严重", "crit": "严重", "致命": "严重", "超危": "严重", "严重": "严重",
    "high": "高危", "高": "高危", "高危": "高危", "高风险": "高危",
    "medium": "中危", "moderate": "中危", "中": "中危", "中危": "中危", "中风险": "中危",
    "low": "低危", "低": "低危", "低危": "低危", "低风险": "低危",
    "info": "信息", "informational": "信息", "信息": "信息", "无风险": "信息",
}


def clean_text(v: object) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def normalize_ip(v: object) -> str:
    s = clean_text(v)
    if not s:
        return ""
    s = re.sub(r"^https?://", "", s, flags=re.I).split("/")[0]
    if s.count(":") == 1 and re.match(r"^[0-9.]+:\d+$", s):
        s = s.rsplit(":", 1)[0]
    try:
        return str(ipaddress.ip_address(s))
    except ValueError:
        return s


def normalize_port(v: object) -> str:
    s = clean_text(v)
    if not s:
        return ""
    m = re.search(r"\d{1,5}", s)
    if not m:
        return s
    n = int(m.group())
    return str(n) if 0 <= n <= 65535 else s


def normalize_cvss(v: object) -> str:
    s = clean_text(v)
    if not s:
        return ""
    m = re.search(r"(?:10(?:\.0+)?|[0-9](?:\.\d+)?)", s)
    if not m:
        return s
    try:
        return f"{float(m.group()):.1f}"
    except ValueError:
        return s


def normalize_severity(v: object, cvss: object = "") -> str:
    s = clean_text(v).lower()
    if s in SEVERITY_MAP:
        return SEVERITY_MAP[s]
    for key, label in SEVERITY_MAP.items():
        if key and key in s:
            return label
    try:
        score = float(normalize_cvss(cvss))
        if score >= 9.0:
            return "严重"
        if score >= 7.0:
            return "高危"
        if score >= 4.0:
            return "中危"
        if score > 0:
            return "低危"
    except (ValueError, TypeError):
        pass
    return clean_text(v)


def normalize_dataframe(
    df: pd.DataFrame,
    source_file: str,
    source_sheet: str,
    mapping_override: Optional[Dict[str, str]] = None,
) -> Tuple[pd.DataFrame, dict]:
    mapping = build_mapping(df.columns)
    if mapping_override:
        valid_cols = {str(c) for c in df.columns}
        valid_fields = set(STANDARD_COLUMNS)
        for source_col, standard_col in mapping_override.items():
            if source_col not in valid_cols:
                continue
            if standard_col == "":
                mapping.pop(source_col, None)
                continue
            if standard_col in valid_fields:
                # One source column maps to one standard field; manual mapping wins.
                for old_source, old_target in list(mapping.items()):
                    if old_target == standard_col and old_source != source_col:
                        del mapping[old_source]
                mapping[source_col] = standard_col

    platform = detect_platform(df.columns)
    result = pd.DataFrame(index=df.index)
    for source_col, standard_col in mapping.items():
        result[standard_col] = df[source_col].map(clean_text)

    for col in STANDARD_COLUMNS:
        if col not in result.columns:
            result[col] = ""

    result["asset_ip"] = result["asset_ip"].map(normalize_ip)
    result["target_url"] = result["target_url"].map(clean_text)
    for index, url in result["target_url"].items():
        if not url:
            continue
        parsed = urlsplit(url if "://" in url else "//" + url)
        host = parsed.hostname or ""
        if host and not result.at[index, "hostname"]:
            result.at[index, "hostname"] = host
        if host and not result.at[index, "asset_ip"]:
            try:
                result.at[index, "asset_ip"] = str(ipaddress.ip_address(host))
            except ValueError:
                pass
        try:
            parsed_port = parsed.port
        except ValueError:
            parsed_port = None
        if parsed_port and not result.at[index, "port"]:
            result.at[index, "port"] = str(parsed_port)
    result["port"] = result["port"].map(normalize_port)
    result["cvss"] = result["cvss"].map(normalize_cvss)
    result["severity"] = [normalize_severity(a, b) for a, b in zip(result["severity"], result["cvss"])]
    result["protocol"] = result["protocol"].str.upper()
    result["source_category"] = detect_source_category(Path(source_file).name, source_sheet)
    result["source_platform"] = platform
    result["source_file"] = Path(source_file).name
    result["source_sheet"] = source_sheet
    header_row = int(df.attrs.get("source_header_row", 0))
    result["original_row"] = [str(i + header_row + 2) for i in range(len(result))]

    unmapped = [str(c) for c in df.columns if str(c) not in mapping]
    metadata = {
        "platform": platform,
        "source_category": result["source_category"].iloc[0] if len(result) else "",
        "header_row": header_row + 1,
        "mapping": mapping,
        "unmapped_columns": unmapped,
        "rows": len(result),
        "source_columns": [str(c) for c in df.columns],
    }
    return result[STANDARD_COLUMNS].copy(), metadata
