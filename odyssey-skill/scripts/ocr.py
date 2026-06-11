from __future__ import annotations

from pathlib import Path
import shutil

from scripts.text_normalize import normalize_chinese_text


def ocr_images(image_paths: list[Path], output_path: Path) -> tuple[str, list[str]]:
    """OCR images with pytesseract when available. Returns text and errors."""
    if not image_paths:
        return "", []
    if not shutil.which("tesseract"):
        return "", ["tesseract_unavailable"]
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:
        return "", [f"ocr_dependency_unavailable:{exc}"]

    texts: list[str] = []
    errors: list[str] = []
    for image_path in image_paths:
        try:
            text = pytesseract.image_to_string(Image.open(image_path), lang="chi_sim+eng")
            if text.strip():
                texts.append(text.strip())
        except Exception as exc:
            errors.append(f"ocr_failed:{image_path}:{exc}")
    merged = normalize_chinese_text("\n\n".join(texts))
    if merged:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(merged, encoding="utf-8")
    return merged, errors
