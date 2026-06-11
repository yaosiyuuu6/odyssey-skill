import importlib.util
import json
from pathlib import Path


def load_script(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upload_records_update_existing_uses_current_record_ids(tmp_path, monkeypatch):
    upload_lark_jsonl = load_script("upload_lark_jsonl")
    jsonl_path = tmp_path / "records.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps({"标题": "A"}, ensure_ascii=False),
                json.dumps({"标题": "B"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )
    calls = []

    monkeypatch.setattr(upload_lark_jsonl, "list_record_ids", lambda *args: ["rec1", "rec2"])
    monkeypatch.setattr(
        upload_lark_jsonl,
        "upsert_record",
        lambda base, table, record, record_id=None: calls.append((record["标题"], record_id)),
    )

    count = upload_lark_jsonl.upload_records("base", "table", jsonl_path, 0, update_existing=True)

    assert count == 2
    assert calls == [("A", "rec1"), ("B", "rec2")]


def test_upload_records_update_existing_rejects_count_mismatch(tmp_path, monkeypatch):
    upload_lark_jsonl = load_script("upload_lark_jsonl")
    jsonl_path = tmp_path / "records.jsonl"
    jsonl_path.write_text(json.dumps({"标题": "A"}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(upload_lark_jsonl, "list_record_ids", lambda *args: ["rec1", "rec2"])

    try:
        upload_lark_jsonl.upload_records("base", "table", jsonl_path, 0, update_existing=True)
    except RuntimeError as exc:
        assert "cannot update existing records" in str(exc)
    else:
        raise AssertionError("expected count mismatch to fail")
