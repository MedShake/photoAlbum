import json

import pytest

from photoalbum import cli
from photoalbum.template_engine import discovery


def write_pack(root, pack_id, templates):
    directory = root / pack_id
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "id": pack_id, "name": pack_id.title(), "version": "1.0",
        "templates": templates,
    }), encoding="utf-8")


def definition(template_id, kinds, **extra):
    return {
        "id": template_id, "name": template_id, "module": "not_imported.by_diagnostics",
        "kinds": kinds, **extra,
    }


def invoke(monkeypatch, capsys, output="table"):
    monkeypatch.setattr("sys.argv", ["photo-album-cli", "templates", "--format", output])
    assert cli.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_templates_discovers_new_pack_and_preserves_declared_compatibility(tmp_path, monkeypatch, capsys):
    # Change only the discovery root; exercise the real loader and registry.
    monkeypatch.setattr(discovery, "_builtin_templates_root", lambda: tmp_path)
    write_pack(tmp_path, "example", [definition(
        "note", ["special_page"],
    )])
    original = json.loads(invoke(monkeypatch, capsys, "json"))
    assert original == [{
        "id": "note", "pack": "example", "kinds": ["special_page"],
        "min_width_mm": None, "max_width_mm": None, "min_height_mm": None, "max_height_mm": None,
        "front": None, "inside_front": None,
        "inside_back": None, "back": None,
    }]

    write_pack(tmp_path, "newcomer", [definition(
        "jacket", ["cover"],
        page_constraints={"min_width_mm": 180, "max_height_mm": 320},
        cover_positions=["front", "back"],
    )])
    rows = json.loads(invoke(monkeypatch, capsys, "json"))
    assert len(rows) == 2
    assert original[0] in rows
    jacket = [row for row in rows if row["id"] == "jacket"]
    assert jacket[0]["min_width_mm"] == 180
    assert jacket[0]["max_height_mm"] == 320
    for row in jacket:
        assert row["pack"] == "newcomer"
        assert row["front"] and row["back"]
        assert not row["inside_front"] and not row["inside_back"]

    table = invoke(monkeypatch, capsys)
    lines = [[cell.strip() for cell in line.split("|")] for line in table.splitlines()]
    assert lines[0] == [
        "ID", "Pack", "Type", "Min Width (mm)", "Max Width (mm)", "Min Height (mm)", "Max Height (mm)",
        "Front", "Inside Front", "Inside Back", "Back",
    ]
    assert lines[1:] == [
        ["note", "example", "special_page", "-", "-", "-", "-", "-", "-", "-", "-"],
        ["jacket", "newcomer", "cover", "180", "-", "-", "320", "yes", "no", "no", "yes"],
    ]


def test_templates_uses_domain_defaults_and_multiple_kinds(tmp_path, monkeypatch, capsys):

    monkeypatch.setattr(discovery, "_builtin_templates_root", lambda: tmp_path)
    write_pack(tmp_path, "unrestricted", [definition("versatile", ["cover", "special_page"])])
    rows = json.loads(invoke(monkeypatch, capsys, "json"))
    assert len(rows) == 1
    assert rows[0]["min_width_mm"] is None
    for row in rows:
        assert row["kinds"] == ["cover", "special_page"]
        assert all(row[key] is True for key in (
            "front", "inside_front", "inside_back", "back",
        ))


def test_templates_empty_discovery(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(discovery, "_builtin_templates_root", lambda: tmp_path)
    assert json.loads(invoke(monkeypatch, capsys, "json")) == []
    assert len(invoke(monkeypatch, capsys).splitlines()) == 1


def test_templates_reports_invalid_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(discovery, "_builtin_templates_root", lambda: tmp_path)
    write_pack(tmp_path, "broken", [definition("bad", ["unknown_kind"])])
    monkeypatch.setattr("sys.argv", ["photo-album-cli", "templates"])
    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown kind" in captured.err


def test_templates_rejects_unknown_output_format():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["templates", "--format", "xml"])
    assert exc.value.code == 2


def test_templates_sorted_by_pack_then_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(discovery, "_builtin_templates_root", lambda: tmp_path)
    write_pack(tmp_path, "zpack", [definition("a", ["special_page"])])
    write_pack(tmp_path, "apack", [definition("z", ["special_page"]), definition("b", ["special_page"])])
    rows = json.loads(invoke(monkeypatch, capsys, "json"))
    assert [(row["pack"], row["id"]) for row in rows] == [("apack", "b"), ("apack", "z"), ("zpack", "a")]
