import importlib.util
import sys
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    skill_root = root / "odyssey-skill"
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_transcribe_audio_uses_no_future_timeout_when_timeout_seconds_is_zero(monkeypatch, tmp_path):
    asr = load_module("asr")
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    seen = {}

    class FakeFuture:
        def result(self, timeout=None):
            seen["timeout"] = timeout
            return {"text": "ok", "assets": [], "errors": []}

        def cancel(self):
            return None

    class FakeExecutor:
        def __init__(self, max_workers):
            seen["max_workers"] = max_workers

        def submit(self, *_args):
            return FakeFuture()

        def shutdown(self, **_kwargs):
            return None

    monkeypatch.setattr(asr, "ProcessPoolExecutor", FakeExecutor)

    result = asr.transcribe_audio(audio_path, tmp_path, timeout_seconds=0)

    assert result["text"] == "ok"
    assert seen["timeout"] is None
