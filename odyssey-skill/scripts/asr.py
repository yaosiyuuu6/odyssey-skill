from __future__ import annotations

import shutil
from concurrent.futures import ProcessPoolExecutor, TimeoutError
import json
from pathlib import Path

from scripts.asr_quality import (
    apply_corrections,
    hotwords_prompt,
    load_hotwords,
    render_speaker_segments,
    speaker_summary,
)
from scripts.text_normalize import normalize_chinese_text


ROOT = Path(__file__).resolve().parents[2]
HOTWORDS_PATH = ROOT / "config" / "hotwords_zh.txt"
CORRECTIONS_PATH = ROOT / "config" / "corrections_zh.json"


def empty_result(errors: list[str] | None = None) -> dict:
    return {
        "text": "",
        "assets": [],
        "errors": errors or [],
        "speaker_segments": [],
        "speaker_count": 0,
        "speaker_role_map": {},
        "speaker_label_status": "unknown",
        "correction_log": [],
    }


def _write_transcript(output_dir: Path, audio_path: Path, transcript: str, suffix: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{audio_path.stem}.{suffix}.transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")
    return [str(transcript_path)]


def _finalize_text(text: str, output_dir: Path, audio_path: Path, suffix: str) -> dict:
    corrected, correction_log = apply_corrections(normalize_chinese_text(text), CORRECTIONS_PATH)
    return {
        "text": corrected,
        "assets": _write_transcript(output_dir, audio_path, corrected, suffix) if corrected else [],
        "errors": [],
        "speaker_segments": [],
        "speaker_count": 0,
        "speaker_role_map": {},
        "speaker_label_status": "unknown",
        "correction_log": correction_log,
    }


def _transcribe_with_mlx(audio_path: Path, output_dir: Path, language: str | None) -> dict:
    try:
        import mlx_whisper  # type: ignore
    except Exception as exc:
        return empty_result([f"mlx_whisper_unavailable:{exc}"])

    try:
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo="mlx-community/whisper-small-mlx",
            language=language,
            verbose=False,
        )
        segments = result.get("segments") or []
        if segments:
            lines = [
                f"[{segment.get('start', 0):.2f}-{segment.get('end', 0):.2f}] A: {segment.get('text', '').strip()}"
                for segment in segments
                if segment.get("text", "").strip()
            ]
            transcript = "\n".join(lines)
        else:
            transcript = result.get("text", "")
        return _finalize_text(transcript, output_dir, audio_path, "mlx")
    except Exception as exc:
        return empty_result([f"mlx_asr_failed:{exc}"])


def _transcribe_with_whisperx(audio_path: Path, output_dir: Path, language: str | None, model: str) -> dict:
    import os

    cache_root = ROOT / ".cache"
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        return empty_result(["whisperx_unavailable:HF_TOKEN_missing"])
    try:
        import torch  # type: ignore
        import whisperx  # type: ignore
    except Exception as exc:
        return empty_result([f"whisperx_unavailable:{exc}"])

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        hotwords = load_hotwords(HOTWORDS_PATH)
        whisper_model = whisperx.load_model(
            model,
            device,
            compute_type=compute_type,
            language=language,
            asr_options={
                "initial_prompt": hotwords_prompt(hotwords),
                "hotwords": " ".join(hotwords),
                "beam_size": 5,
                "best_of": 5,
                "condition_on_previous_text": False,
            },
        )
        result = whisper_model.transcribe(
            str(audio_path),
            batch_size=8,
            language=language,
        )
        align_model, metadata = whisperx.load_align_model(language_code=language or result.get("language", "zh"), device=device)
        aligned = whisperx.align(result["segments"], align_model, metadata, str(audio_path), device, return_char_alignments=False)
        from whisperx.diarize import DiarizationPipeline  # type: ignore

        diarize_model = DiarizationPipeline(token=hf_token, device=device)
        diarize_segments = diarize_model(str(audio_path))
        assigned = whisperx.assign_word_speakers(diarize_segments, aligned)
        speaker_segments = []
        for segment in assigned.get("segments", []):
            text = normalize_chinese_text(str(segment.get("text", "")).strip())
            if not text:
                continue
            speaker_segments.append(
                {
                    "start": float(segment.get("start", 0.0) or 0.0),
                    "end": float(segment.get("end", 0.0) or 0.0),
                    "speaker": str(segment.get("speaker") or "SPEAKER_UNKNOWN"),
                    "text": text,
                }
            )
        transcript = render_speaker_segments(speaker_segments)
        corrected, correction_log = apply_corrections(transcript, CORRECTIONS_PATH)
        speaker_count, speaker_role_map = speaker_summary(speaker_segments)
        assets = _write_transcript(output_dir, audio_path, corrected, "whisperx")
        json_path = output_dir / f"{audio_path.stem}.whisperx.json"
        json_path.write_text(
            json.dumps(
                {"segments": speaker_segments, "text": corrected},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        assets.append(str(json_path))
        return {
            "text": corrected,
            "assets": assets,
            "errors": [],
            "speaker_segments": speaker_segments,
            "speaker_count": speaker_count,
            "speaker_role_map": speaker_role_map,
            "speaker_label_status": "diarized" if speaker_count else "unknown",
            "correction_log": correction_log,
        }
    except Exception as exc:
        return empty_result([f"whisperx_failed:{exc}"])


def _transcribe_audio_impl(audio_path_text: str, output_dir_text: str, language: str | None, engine: str, model: str) -> dict:
    audio_path = Path(audio_path_text)
    output_dir = Path(output_dir_text)
    errors: list[str] = []
    if not audio_path.exists():
        return empty_result([f"audio_missing:{audio_path}"])

    if engine == "whisperx":
        whisperx_result = _transcribe_with_whisperx(audio_path, output_dir, language, model)
        if whisperx_result["text"]:
            return whisperx_result
        errors.extend(whisperx_result["errors"])

    if engine in {"auto", "mlx"}:
        mlx_result = _transcribe_with_mlx(audio_path, output_dir, language)
        if mlx_result["text"] or engine == "mlx":
            mlx_result["errors"] = errors + mlx_result["errors"]
            return mlx_result
        errors.extend(mlx_result["errors"])

    if engine not in {"auto", "faster-whisper"}:
        if engine != "whisperx":
            return empty_result([f"unsupported_asr_engine:{engine}"])

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        return empty_result(errors + [f"faster_whisper_unavailable:{exc}"])

    try:
        whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
        hotwords = " ".join(load_hotwords(HOTWORDS_PATH))
        segments, _info = whisper_model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False,
            initial_prompt=hotwords_prompt(load_hotwords(HOTWORDS_PATH)),
            hotwords=hotwords,
        )
        lines = []
        for segment in segments:
            speaker = "A"
            lines.append(f"[{segment.start:.2f}-{segment.end:.2f}] {speaker}: {segment.text.strip()}")
        result = _finalize_text("\n".join(line for line in lines if line.strip()), output_dir, audio_path, "faster_whisper")
        result["errors"] = errors
        return result
    except Exception as exc:
        return empty_result(errors + [f"asr_failed:{exc}"])


def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    language: str | None = None,
    timeout_seconds: int = 900,
    engine: str = "auto",
    model: str = "base",
) -> dict:
    """Transcribe audio with faster-whisper when available.

    Returns transcript text, generated asset paths, and non-fatal errors.
    """
    try:
        executor = ProcessPoolExecutor(max_workers=1)
    except PermissionError:
        return _transcribe_audio_impl(str(audio_path), str(output_dir), language, engine, model)

    future = executor.submit(_transcribe_audio_impl, str(audio_path), str(output_dir), language, engine, model)
    timeout = None if timeout_seconds <= 0 else timeout_seconds
    try:
        result = future.result(timeout=timeout)
        executor.shutdown(wait=True)
        return result
    except TimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        return empty_result([f"asr_timeout:{timeout_seconds}s"])


def find_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    local = Path.cwd() / ".venv" / "bin" / name
    if local.exists():
        return str(local)
    return None
