from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
from zipfile import BadZipFile, ZipFile

import pandas as pd

from adapters.field_mapper import header_match_score

MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_ROWS = 200_000
MAX_SHEETS = 100


def _validate_path(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"文件不存在或不是普通文件：{path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"文件超过 50 MB 限制：{path.name}")


def _validate_workbook_archive(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            total = sum(item.file_size for item in entries)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError(f"工作簿解压后超过 250 MB 限制：{path.name}")
            for item in entries:
                if item.compress_size and item.file_size / item.compress_size > 200:
                    raise ValueError(f"工作簿压缩比异常，已拒绝读取：{path.name}")
    except BadZipFile as exc:
        raise ValueError(f"工作簿格式损坏：{path.name}") from exc


def _validate_frames(path: Path, frames: List[Tuple[str, pd.DataFrame]]) -> List[Tuple[str, pd.DataFrame]]:
    if len(frames) > MAX_SHEETS:
        raise ValueError(f"工作簿 Sheet 数超过 {MAX_SHEETS}：{path.name}")
    total_rows = sum(len(frame) for _, frame in frames)
    if total_rows > MAX_ROWS:
        raise ValueError(f"总记录数超过 {MAX_ROWS:,} 条限制：{path.name}")
    return frames


def _unique_headers(values: list[object]) -> list[str]:
    headers, used = [], set()
    for index, value in enumerate(values, start=1):
        base = str(value or "").strip() or f"未命名列_{index}"
        name, suffix = base, 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        headers.append(name)
        used.add(name)
    return headers


def _promote_header(raw: pd.DataFrame) -> pd.DataFrame:
    """Find customer-table headers even when title/date rows appear above them."""
    if raw.empty:
        return raw
    best_index, best_score, best_filled = 0, -1, -1
    for index in range(min(20, len(raw))):
        values = [value for value in raw.iloc[index].tolist() if str(value or "").strip()]
        score = header_match_score(values)
        filled = len(values)
        if (score, filled) > (best_score, best_filled):
            best_index, best_score, best_filled = index, score, filled
    # Two recognized fields are a strong header. Otherwise keep the first row,
    # preserving compatibility with uncommon tables that need manual mapping.
    header_index = best_index if best_score >= 2 else 0
    data = raw.iloc[header_index + 1:].copy()
    data.columns = _unique_headers(raw.iloc[header_index].tolist())
    data = data.replace(r"^\s*$", pd.NA, regex=True).dropna(axis=0, how="all").dropna(axis=1, how="all").fillna("")
    data.attrs["source_header_row"] = header_index
    return data.reset_index(drop=True)


def _read_csv(path: Path) -> pd.DataFrame:
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            raw = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False, header=None)
            return _promote_header(raw)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return _promote_header(pd.read_csv(path, dtype=str, keep_default_na=False, header=None))


def read_input(path_str: str) -> List[Tuple[str, pd.DataFrame]]:
    path = Path(path_str)
    _validate_path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _validate_frames(path, [("CSV", _read_csv(path))])
    if suffix in {".xlsx", ".xlsm"}:
        _validate_workbook_archive(path)
        sheets = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False, header=None, engine="openpyxl")
        return _validate_frames(path, [(str(name), _promote_header(df)) for name, df in sheets.items()])
    if suffix == ".xls":
        sheets = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False, header=None, engine="xlrd")
        return _validate_frames(path, [(str(name), _promote_header(df)) for name, df in sheets.items()])
    raise ValueError(f"不支持的文件格式: {suffix}，仅支持 CSV/XLS/XLSX/XLSM")
