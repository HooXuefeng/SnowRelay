"""Create a source-only SnowRelay upload directory without local runtimes or results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "SnowRelay-GitHub"
ARCHIVE = ROOT.parent / "SnowRelay-GitHub.zip"
AUDIT = ROOT.parent / "SnowRelay-GitHub-manifest.json"
SOURCE_DIRS = {
    "adapters", "app", "assets", "build_hooks", "design", "exporters",
    "models", "processors", "rules", "samples", "scripts", "tests",
}
SOURCE_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".png", ".ico", ".ps1", ".bat", ".csv"}
ROOT_FILES = {
    ".gitignore", "README.md", "CHANGELOG.md", "VERSION", "main.py",
    "requirements.txt", "requirements-build.txt", "SnowRelay.spec",
    "start.bat", "install.bat", "build_exe.bat", "LICENSE", "THIRD_PARTY_NOTICES.md",
}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".runtime", ".venv", ".build-env", ".build-python", "build", "dist"}


def selected_files() -> list[Path]:
    selected = {ROOT / name for name in ROOT_FILES}
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            relative = path.relative_to(ROOT)
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and not set(relative.parts) & EXCLUDED_PARTS:
                selected.add(path)
    return sorted(path for path in selected if path.is_file())


def main() -> None:
    if DEST.exists() or ARCHIVE.exists():
        raise SystemExit("Upload output already exists; remove it before rebuilding.")
    selected = selected_files()
    problems = []
    for path in selected:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f"Unexpected source link: {path}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
            problems.append(path.relative_to(ROOT).as_posix())
        if re.search(r"(?im)^\s*(?:API_KEY|SECRET_KEY|TOKEN|PASSWORD)\s*=\s*[^\s#]{12,}\s*$", text):
            problems.append(path.relative_to(ROOT).as_posix())
    if problems:
        raise RuntimeError("Review sensitive content in: " + ", ".join(sorted(set(problems))))

    DEST.mkdir()
    manifest = []
    for source in selected:
        relative = source.relative_to(ROOT)
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append({"path": relative.as_posix(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    with zipfile.ZipFile(ARCHIVE, "x", zipfile.ZIP_DEFLATED) as bundle:
        for entry in manifest:
            bundle.write(DEST / entry["path"], "SnowRelay/" + entry["path"])
    AUDIT.write_text(json.dumps({"files": manifest, "source_only": True, "secret_scan": "passed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"folder": str(DEST), "archive": str(ARCHIVE), "files": len(manifest), "bytes": ARCHIVE.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
