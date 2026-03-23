from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "web" / "node_modules" / "katex" / "dist"
TARGET_ROOT = REPO_ROOT / "web" / "public" / "vendor" / "katex"
REQUIRED_FILES = (
    Path("katex.min.css"),
    Path("katex.min.js"),
    Path("contrib") / "auto-render.min.js",
    Path("contrib") / "copy-tex.min.js",
)


def copy_required_file(relative_path: Path) -> None:
    source_path = SOURCE_ROOT / relative_path
    if not source_path.is_file():
        raise FileNotFoundError(f"Missing KaTeX runtime asset: {source_path}")
    target_path = TARGET_ROOT / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def copy_fonts() -> None:
    source_fonts_dir = SOURCE_ROOT / "fonts"
    if not source_fonts_dir.is_dir():
        raise FileNotFoundError(f"Missing KaTeX fonts directory: {source_fonts_dir}")

    target_fonts_dir = TARGET_ROOT / "fonts"
    if target_fonts_dir.exists():
        shutil.rmtree(target_fonts_dir)
    shutil.copytree(source_fonts_dir, target_fonts_dir)


def main() -> int:
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)

    for relative_path in REQUIRED_FILES:
        copy_required_file(relative_path)
    copy_fonts()

    print(f"Synced KaTeX runtime assets to {TARGET_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
