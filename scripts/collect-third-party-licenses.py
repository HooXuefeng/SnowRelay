from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import shutil
import sys
from pathlib import Path


PACKAGES = (
    "pandas", "numpy", "openpyxl", "et-xmlfile", "xlrd", "tkinterdnd2",
    "Pillow", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile", "pywin32-ctypes",
)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "package"


def license_files(dist) -> list[Path]:
    candidates = []
    for name in dist.metadata.get_all("License-File") or []:
        path = Path(dist.locate_file(name))
        if path.is_file():
            candidates.append(path)
    if not candidates:
        for item in dist.files or []:
            if re.match(r"(?i)^(license|copying|notice)(\..*)?$", Path(item).name):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    candidates.append(path)
    return list(dict.fromkeys(path.resolve() for path in candidates))


def license_label(dist) -> str:
    expression = (dist.metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    raw = (dist.metadata.get("License") or "").strip()
    if raw and "\n" not in raw and len(raw) <= 120:
        return raw
    classifiers = dist.metadata.get_all("Classifier") or []
    values = [item.rsplit("::", 1)[-1].strip() for item in classifiers if item.startswith("License ::")]
    return ", ".join(values) or "见随附许可证"


def collect(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copyfile(python_license, output / "Python.LICENSE.txt")
    for package in PACKAGES:
        try:
            dist = metadata.distribution(package)
        except metadata.PackageNotFoundError:
            continue
        name = dist.metadata.get("Name") or package
        expression = license_label(dist)
        homepage = (dist.metadata.get("Home-page") or "").replace("|", "%7C").replace("\n", " ")[:300]
        copied = []
        for index, source in enumerate(license_files(dist), 1):
            suffix = "" if index == 1 else f"-{index}"
            destination = output / f"{safe_name(name)}{suffix}.{safe_name(source.name)}"
            shutil.copyfile(source, destination); copied.append(destination.name)
        rows.append((name, dist.version, expression.replace("|", "\\|").replace("\n", " "), homepage, ", ".join(copied) or "包元数据"))
    lines = ["# SnowRelay 构建依赖许可证索引", "", "此目录由构建脚本根据实际打包环境生成。项目自身许可证位于发布目录根部 `LICENSE`。", "", "| 组件 | 版本 | 许可证元数据 | 上游地址 | 随附文件 |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {name} | {version} | {expression} | {homepage} | {files} |" for name, version, expression, homepage, files in rows)
    (output / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("output", type=Path); args = parser.parse_args()
    collect(args.output.resolve())
