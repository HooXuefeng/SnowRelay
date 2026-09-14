from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


SUPPORTED_INPUT_SUFFIXES = frozenset({".csv", ".xls", ".xlsx", ".xlsm"})


def classify_input_paths(paths: Iterable[str | os.PathLike[str]]) -> tuple[list[str], list[str]]:
    """Return unique supported files and readable rejection messages."""
    accepted: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()

    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            rejected.append(f"{path.name or path}（文件不存在）")
            continue
        if not path.is_file():
            rejected.append(f"{path.name or path}（暂不支持文件夹）")
            continue
        if path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            rejected.append(f"{path.name}（不支持 {path.suffix or '无扩展名'} 格式）")
            continue

        normalized = str(path.resolve())
        identity = os.path.normcase(normalized)
        if identity in seen:
            continue
        seen.add(identity)
        accepted.append(normalized)

    return accepted, rejected
