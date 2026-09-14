from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterable, Set

import pandas as pd

WEAK_KEYWORDS = (
    "弱口令", "弱密码", "默认口令", "默认密码", "空口令", "空密码",
    "weak password", "default password", "default credential", "blank password",
    "password vulnerability", "口令过弱",
)


def _read_lines(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    values = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            values.add(line)
    return values


def load_rules(rule_dir: str | Path) -> Dict[str, Set[str]]:
    rule_dir = Path(rule_dir)
    ports = {re.sub(r"\D", "", x) for x in _read_lines(rule_dir / "high_ports.txt")}
    ports.discard("")
    weak_passwords = _read_lines(rule_dir / "weak_passwords.txt")
    high_cves = {x.upper() for x in _read_lines(rule_dir / "high_vulnerabilities.txt")}
    return {"ports": ports, "weak_passwords": weak_passwords, "high_cves": high_cves}


def _extract_cves(text: str) -> Set[str]:
    return {x.upper() for x in re.findall(r"CVE-\d{4}-\d{4,7}", text or "", flags=re.I)}


def classify(df: pd.DataFrame, rules: Dict[str, Set[str]]) -> pd.DataFrame:
    out = df.copy()
    flags_vuln, flags_port, flags_weak, credential_states, types, reasons = [], [], [], [], [], []

    for _, row in out.iterrows():
        sev = str(row.get("severity", "")).strip()
        name = str(row.get("vuln_name", ""))
        desc = str(row.get("description", ""))
        evidence = str(row.get("evidence", ""))
        user = str(row.get("username", "")).strip()
        password = str(row.get("password", "")).strip()
        source_category = str(row.get("source_category", "")).strip()
        port = re.sub(r"\D", "", str(row.get("port", "")))
        cves = _extract_cves(" ".join([str(row.get("cve", "")), name, desc, evidence]))

        try:
            cvss = float(str(row.get("cvss", "")).strip())
        except ValueError:
            cvss = -1.0

        high_vuln = source_category == "高危漏洞" or sev in {"严重", "高危"} or cvss >= 7.0 or bool(cves & rules["high_cves"])
        high_port = source_category == "高危端口" or bool(port and port in rules["ports"])

        combined = " ".join([name, desc, evidence]).lower()
        keyword_match = any(k.lower() in combined for k in WEAK_KEYWORDS)
        dictionary_match = bool(password and password in rules["weak_passwords"])
        weak = source_category == "弱口令" or keyword_match or dictionary_match
        if weak:
            credential_status = "已识别弱口令"
        elif password:
            credential_status = "发现凭据（待核验）"
        elif user:
            credential_status = "仅发现账号"
        else:
            credential_status = "未发现凭据"

        labels, why = [], []
        if high_vuln:
            labels.append("高危漏洞")
            if source_category == "高危漏洞":
                why.append("客户原表分类=高危漏洞")
            elif sev in {"严重", "高危"}:
                why.append(f"风险等级={sev}")
            elif cvss >= 7.0:
                why.append(f"CVSS={cvss:g}")
            elif cves & rules["high_cves"]:
                why.append("命中高危CVE规则")
        if high_port:
            labels.append("高危端口")
            if source_category == "高危端口":
                why.append("客户原表分类=高危端口")
            else:
                why.append(f"端口={port}命中规则")
        if weak:
            labels.append("弱口令")
            if source_category == "弱口令":
                why.append("客户原表分类=弱口令")
            if dictionary_match:
                why.append("口令命中弱口令字典")
            if keyword_match:
                why.append("命中弱口令关键词")
        elif password:
            why.append("发现口令字段，尚未确认是否为有效弱口令")

        flags_vuln.append("是" if high_vuln else "否")
        flags_port.append("是" if high_port else "否")
        flags_weak.append("是" if weak else "否")
        credential_states.append(credential_status)
        types.append("、".join(labels))
        reasons.append("；".join(dict.fromkeys(why)))

    out["is_high_vulnerability"] = flags_vuln
    out["is_high_risk_port"] = flags_port
    out["is_weak_password"] = flags_weak
    out["credential_status"] = credential_states
    out["risk_type"] = types
    out["match_reason"] = reasons
    return out


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    keys = ["asset_ip", "port", "protocol", "vuln_name", "cve", "username", "password", "risk_type"]
    existing = [k for k in keys if k in df.columns]
    return df.drop_duplicates(subset=existing, keep="first").reset_index(drop=True)
