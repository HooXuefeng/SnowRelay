from __future__ import annotations

import re
from typing import Dict, Iterable

FIELD_ALIASES = {
    "asset_ip": [
        "asset_ip", "ip", "ip地址", "资产ip", "资产地址", "主机ip", "目标ip", "目标地址",
        "host", "host ip", "host_ip", "target", "target ip", "target_ip", "address", "漏洞ip",
        "影响ip", "受影响ip", "设备ip", "服务器ip",
    ],
    "hostname": ["hostname", "host name", "主机名", "域名", "资产名称", "目标名称", "网站域名"],
    "target_url": [
        "url", "target url", "target_url", "漏洞url", "目标url", "网站url", "web地址",
        "漏洞地址", "访问地址", "请求地址", "漏洞位置", "链接", "网址",
    ],
    "port": ["port", "端口", "端口号", "service port", "dst port", "目的端口", "目标端口", "开放端口", "危险端口"],
    "protocol": ["protocol", "proto", "协议", "网络协议", "传输协议"],
    "service": ["service", "service name", "服务", "服务名称", "应用服务", "application", "端口服务", "服务类型"],
    "severity": [
        "severity", "risk", "risk level", "risk_level", "level", "风险", "风险等级", "危险等级",
        "威胁等级", "严重程度", "漏洞等级", "危害等级",
    ],
    "cvss": ["cvss", "cvss score", "cvss_score", "cvssv3", "cvss v3", "基础评分", "评分"],
    "vuln_name": [
        "name", "plugin name", "vuln name", "vulnerability", "vulnerability name", "nvt name",
        "漏洞名称", "漏洞标题", "风险名称", "问题名称", "弱点名称", "检测项", "标题", "漏洞类型", "问题类型",
    ],
    "cve": ["cve", "cves", "cve id", "cve_id", "cve编号"],
    "cnvd": ["cnvd", "cnvd编号"],
    "cnnvd": ["cnnvd", "cnnvd编号"],
    "username": ["username", "user", "account", "用户名", "用户", "账号", "账户", "登录账号", "弱口令账号"],
    "password": ["password", "passwd", "pwd", "密码", "口令", "弱口令", "默认口令", "登录密码", "弱密码"],
    "description": [
        "description", "desc", "synopsis", "summary", "vulnerability description", "漏洞描述",
        "问题描述", "风险描述", "漏洞详情", "详细信息", "描述",
    ],
    "evidence": [
        "evidence", "result", "output", "plugin output", "proof", "detail", "检测结果", "验证信息",
        "证据", "结果", "返回结果", "扫描结果", "漏洞证明", "验证结果", "测试结果", "响应信息",
    ],
    "solution": [
        "solution", "remediation", "fix", "recommendation", "修复建议", "解决方案", "整改建议",
        "处置建议", "修复方案",
    ],
}

PLATFORM_HINTS = {
    "Nessus": {"plugin id", "plugin name", "plugin output", "risk", "host"},
    "Greenbone/OpenVAS": {"nvt name", "severity", "cvss", "ip"},
    "Nuclei": {"template-id", "matched-at", "matcher-name"},
    "绿盟": {"漏洞名称", "危险等级", "主机ip", "漏洞描述", "修复建议"},
    "奇安信": {"漏洞名称", "风险等级", "资产ip", "漏洞详情"},
    "启明星辰": {"漏洞名称", "威胁等级", "目标ip", "解决方案"},
}


def normalize_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-_/\\:：()（）\[\]【】]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


NORMALIZED_ALIASES = {
    field: {normalize_header(alias) for alias in aliases}
    for field, aliases in FIELD_ALIASES.items()
}

CATEGORY_MARKERS = {
    "高危漏洞": ("高危漏洞", "严重漏洞", "重大漏洞", "high vulnerability", "high risk vulnerability"),
    "高危端口": ("高危端口", "危险端口", "风险端口", "high risk port", "high port"),
    "弱口令": ("弱口令", "弱密码", "默认口令", "默认密码", "weak password", "weak credential"),
}


def detect_platform(columns: Iterable[object]) -> str:
    normalized = {normalize_header(c) for c in columns}
    best_name = "通用表格"
    best_score = 0
    for name, hints in PLATFORM_HINTS.items():
        score = len(normalized & {normalize_header(x) for x in hints})
        if score > best_score:
            best_name = name
            best_score = score
    return best_name if best_score >= 2 else "通用表格"


def header_match_score(values: Iterable[object]) -> int:
    """Score a possible header row by distinct SnowRelay fields it identifies."""
    return len(set(build_mapping(values).values()))


def detect_source_category(source_file: str, sheet: str) -> str:
    text = normalize_header(f"{source_file} {sheet}")
    matches = [label for label, markers in CATEGORY_MARKERS.items() if any(normalize_header(x) in text for x in markers)]
    return matches[0] if len(matches) == 1 else ""


def build_mapping(columns: Iterable[object]) -> Dict[str, str]:
    """Return {source_column: standard_field}. Exact aliases first, fuzzy fallback second."""
    mapping: Dict[str, str] = {}
    used = set()
    for col in columns:
        n = normalize_header(col)
        for field, aliases in NORMALIZED_ALIASES.items():
            if field in used:
                continue
            if n in aliases:
                mapping[str(col)] = field
                used.add(field)
                break

    # Conservative fuzzy matching for common prefixed/suffixed headers.
    for col in columns:
        if str(col) in mapping:
            continue
        n = normalize_header(col)
        for field, aliases in NORMALIZED_ALIASES.items():
            if field in used:
                continue
            if any(len(a) >= 3 and (n.startswith(a + " ") or n.endswith(" " + a)) for a in aliases):
                mapping[str(col)] = field
                used.add(field)
                break
    return mapping
