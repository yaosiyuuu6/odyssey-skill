MEDIA_PLATFORMS = {"bilibili", "podcast"}


def evaluate_text_completeness(record: dict) -> str:
    """Return 完整 / 部分 / 缺失 using platform-specific minimum evidence."""
    platform = record.get("platform")
    body = (record.get("body_text") or "").strip()
    ocr = (record.get("ocr_text") or "").strip()
    transcript = (record.get("transcript_text") or "").strip()
    notes = set(record.get("notes") or [])
    assets = record.get("assets") or {}
    errors = record.get("fetch_errors") or []

    if "metadata_description_only" in notes and not transcript and not ocr:
        return "缺失"

    if platform in MEDIA_PLATFORMS:
        if transcript and not errors:
            return "完整"
        if transcript:
            return "部分"
        return "缺失"

    if platform == "xiaohongshu":
        images = (assets.get("images") or []) + (assets.get("remote_images") or [])
        image_ocr_required = bool(images) or "image_ocr_pending" in notes
        if body and (not images or ocr):
            return "完整"
        if body and image_ocr_required and not ocr:
            return "部分"
        if body or ocr or image_ocr_required:
            return "部分"
        return "缺失"

    if body or ocr or transcript:
        return "部分"
    return "缺失"
