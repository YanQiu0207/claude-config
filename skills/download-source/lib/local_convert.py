"""本地文件转换：

  EPUB         → ebooklib + BeautifulSoup
  PDF/DOCX/PPTX/XLSX/CSV/JSON/XML/JPG/PNG/MP3/WAV/ZIP → markitdown
  MD/TXT       → 直接复制

输出统一落到 out_dir/ 下，文件名为 content.md（除 MD/TXT 保留原扩展名）。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    from markitdown import MarkItDown  # type: ignore
except ImportError:  # pragma: no cover
    MarkItDown = None

try:
    import ebooklib  # type: ignore
    from ebooklib import epub  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    ebooklib = None
    epub = None
    BeautifulSoup = None


@dataclass
class LocalResult:
    success: bool
    title: str = ""
    files: list[str] = field(default_factory=list)
    strategy_used: str = ""
    error: str = ""


# 走 markitdown 的扩展名集合
MARKITDOWN_EXTS = {
    ".pdf",
    ".docx", ".pptx", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".mp3", ".wav",
    ".zip",
    ".csv", ".json", ".xml", ".html", ".htm",
}

# 直接复制的扩展名集合
COPY_EXTS = {".md", ".txt"}


def convert_local(file_path: Path, out_dir: Path) -> LocalResult:
    """把本地文件转换/复制到 out_dir/。"""
    if not file_path.exists():
        return LocalResult(
            success=False,
            strategy_used="local_missing",
            error=f"File not found: {file_path}",
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    if suffix == ".epub":
        return _convert_epub(file_path, out_dir)
    if suffix in COPY_EXTS:
        return _copy_text(file_path, out_dir)
    if suffix in MARKITDOWN_EXTS:
        return _convert_markitdown(file_path, out_dir)

    return LocalResult(
        success=False,
        strategy_used="local_unsupported",
        error=f"Unsupported extension: {suffix}",
    )


def _convert_epub(file_path: Path, out_dir: Path) -> LocalResult:
    if epub is None or BeautifulSoup is None:
        return LocalResult(
            success=False,
            strategy_used="ebooklib_missing",
            error="ebooklib / beautifulsoup4 not installed",
        )
    try:
        book = epub.read_epub(str(file_path))
    except Exception as e:  # noqa: BLE001
        return LocalResult(
            success=False,
            strategy_used="ebooklib_failed",
            error=f"{type(e).__name__}: {e}",
        )

    title = ""
    try:
        meta = book.get_metadata("DC", "title")
        if meta:
            title = str(meta[0][0])
    except Exception:  # noqa: BLE001
        pass
    if not title:
        title = file_path.stem

    parts = []
    for item in book.get_items():
        try:
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                parts.append(soup.get_text())
        except Exception:  # noqa: BLE001
            continue

    md_path = out_dir / "content.md"
    md_path.write_text(
        f"# {title}\n\nSource file: {file_path.name}\n\n" + "\n\n".join(parts),
        encoding="utf-8",
    )
    return LocalResult(
        success=True,
        title=title,
        files=[str(md_path)],
        strategy_used="ebooklib",
    )


def _copy_text(file_path: Path, out_dir: Path) -> LocalResult:
    target = out_dir / file_path.name
    shutil.copy2(file_path, target)
    title = file_path.stem
    try:
        head = target.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in head[:30]:
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break
    except OSError:
        pass
    return LocalResult(
        success=True,
        title=title,
        files=[str(target)],
        strategy_used="copy",
    )


def _convert_markitdown(file_path: Path, out_dir: Path) -> LocalResult:
    if MarkItDown is None:
        return LocalResult(
            success=False,
            strategy_used="markitdown_missing",
            error="markitdown not installed. Run: pip install 'markitdown[all]'",
        )
    try:
        md = MarkItDown()
        result = md.convert(str(file_path))
    except Exception as e:  # noqa: BLE001
        return LocalResult(
            success=False,
            strategy_used="markitdown_failed",
            error=f"{type(e).__name__}: {e}",
        )

    text = getattr(result, "text_content", "") or getattr(result, "markdown", "") or ""
    title = getattr(result, "title", "") or file_path.stem

    out_path = out_dir / "content.md"
    out_path.write_text(
        f"# {title}\n\nSource file: {file_path.name}\n\n{text}",
        encoding="utf-8",
    )
    return LocalResult(
        success=True,
        title=title,
        files=[str(out_path)],
        strategy_used="markitdown",
    )
