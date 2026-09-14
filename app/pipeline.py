from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from adapters.file_reader import read_input
from processors.normalizer import normalize_dataframe
from processors.rule_engine import classify, deduplicate, load_rules
from exporters.excel_exporter import export_excel
from exporters.snowedge_exporter import export_snowedge_package

ProgressCallback = Optional[Callable[[str], None]]
MappingOverrides = Optional[Dict[str, Dict[str, str]]]


def mapping_key(path: str, sheet: str) -> str:
    return f"{path}::{sheet}"


def inspect_inputs(input_files: Iterable[str]) -> List[dict]:
    """Read headers and auto-mapping metadata without running rule classification."""
    results: List[dict] = []
    for path in input_files:
        for sheet, df in read_input(path):
            if df.empty:
                continue
            _, meta = normalize_dataframe(df.head(1), path, sheet)
            meta.update({"file": path, "sheet": sheet, "rows": len(df)})
            results.append(meta)
    return results


def process_files(
    input_files: Iterable[str],
    rule_dir: str,
    mapping_overrides: MappingOverrides = None,
    progress: ProgressCallback = None,
) -> Tuple[pd.DataFrame, List[dict]]:
    files = list(input_files)
    if not files:
        raise ValueError("请至少选择一个输入文件。")

    rules = load_rules(rule_dir)
    frames, metadata = [], []
    mapping_overrides = mapping_overrides or {}

    for path in files:
        if progress:
            progress(f"读取：{path}")
        for sheet, df in read_input(path):
            if df.empty:
                continue
            override = mapping_overrides.get(mapping_key(path, sheet), {})
            normalized, meta = normalize_dataframe(df, path, sheet, mapping_override=override)
            classified = classify(normalized, rules)
            frames.append(classified)
            meta.update({"file": path, "sheet": sheet})
            metadata.append(meta)

    if not frames:
        raise ValueError("未读取到有效数据。")

    merged = deduplicate(pd.concat(frames, ignore_index=True))
    if progress:
        progress(f"标准化完成：{len(merged)} 条")
    return merged, metadata


def export_result(
    df: pd.DataFrame,
    output_file: str,
    input_files: Iterable[str],
    mask_passwords: bool = True,
    progress: ProgressCallback = None,
) -> None:
    if progress:
        progress("正在生成标准 Excel…")
    export_excel(df, output_file, list(input_files), mask_passwords=mask_passwords)
    if progress:
        progress(f"导出完成：{output_file}")


def export_to_snowedge(
    df: pd.DataFrame,
    output_file: str,
    input_files: Iterable[str],
    progress: ProgressCallback = None,
) -> None:
    if progress:
        progress("正在生成 SnowEdge 联动包…")
    export_snowedge_package(df, output_file, list(input_files))
    if progress:
        progress(f"联动包完成：{output_file}")


def run_pipeline(
    input_files: Iterable[str],
    output_file: str,
    rule_dir: str,
    mask_passwords: bool = True,
    progress: ProgressCallback = None,
    mapping_overrides: MappingOverrides = None,
) -> Tuple[pd.DataFrame, List[dict]]:
    files = list(input_files)
    df, metadata = process_files(files, rule_dir, mapping_overrides=mapping_overrides, progress=progress)
    export_result(df, output_file, files, mask_passwords=mask_passwords, progress=progress)
    return df, metadata
