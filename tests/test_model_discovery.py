"""
Model auto-discovery + default/fallback selection in web_ui/server.py:
  discover_models(), _file_sort_key(), get_default_choice(), get_model() fallback,
  and the /api/models `default` field.

The configured default opponent is the strongest *stable* league checkpoint
(stage_13_stage13_final), never the experimental v2 group.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import web_ui.server as S
from web_ui.server import app, discover_models, _file_sort_key, get_default_choice, MODELS_DIR

client = TestClient(app)


# ── discover_models ────────────────────────────────────────────────────────

def test_discover_models_matches_zip_files_on_disk():
    zips = list(MODELS_DIR.rglob("*.zip"))
    models = discover_models()
    assert len(models) == len(zips) > 0
    for m in models:
        assert {"id", "label", "group", "path"} <= set(m)
        assert isinstance(m["id"], str) and isinstance(m["label"], str)


def test_discover_models_group_is_parent_folder():
    models = {m["id"]: m for m in discover_models()}
    assert "stage_13_stage13_final" in models
    m = models["stage_13_stage13_final"]
    # `group` is the raw parent-folder name (note: folders may contain spaces,
    # e.g. "stage 13"); the id replaces spaces with underscores.
    assert m["group"] == Path(m["path"]).parent.name
    assert m["group"] == "stage 13"


def test_discover_models_ids_unique():
    ids = [m["id"] for m in discover_models()]
    assert len(ids) == len(set(ids))


# ── _file_sort_key ─────────────────────────────────────────────────────────

def test_file_sort_key_buckets():
    assert _file_sort_key("foo_final")[0] == 0
    assert _file_sort_key("foo_latest")[0] == 0
    assert _file_sort_key("final")[0] == 0
    assert _file_sort_key("model_v7")[0] == 1
    assert _file_sort_key("randomname")[0] == 2


def test_file_sort_key_ordering():
    # final/latest first, then versions DESCENDING, then plain names
    assert _file_sort_key("m_final") < _file_sort_key("m_v5") < _file_sort_key("zzz")
    assert _file_sort_key("m_v10") < _file_sort_key("m_v2")   # higher version sorts earlier


def test_discovered_group_sorts_final_first():
    # within the peter_local group, the final/latest entries come before vN entries
    peter = [m for m in discover_models() if m["group"] == "peter_local"]
    if len(peter) >= 2:
        # the first peter entry should be a final/latest if one exists in the group
        stems = [Path(m["path"]).stem for m in peter]
        if any(s.endswith(("_final", "_latest")) for s in stems):
            assert peter[0]["path"].stem.endswith(("_final", "_latest"))


# ── get_default_choice (configured + fallback logic) ───────────────────────

def test_default_is_configured_stable_model():
    d = get_default_choice()
    assert d is not None
    assert d["id"] in S.DEFAULT_MODEL_PREFERENCES        # one of the stable picks
    assert d["id"] == "stage_13_stage13_final"           # top preference present on disk
    assert d["group"] != "v2"                            # never the experimental default


def test_default_prefers_stable_over_first(monkeypatch):
    fake = [
        {"id": "v2_v2_final", "label": "v2", "group": "v2"},          # would be first
        {"id": "stage_13_stage13_final", "label": "s13", "group": "stage_13"},
    ]
    monkeypatch.setattr(S, "_discovered", fake)
    assert get_default_choice()["id"] == "stage_13_stage13_final"     # preferred, not first


def test_default_falls_back_to_first_when_no_preferred(monkeypatch):
    fake = [{"id": "alpha", "label": "a", "group": "x"},
            {"id": "beta", "label": "b", "group": "y"}]
    monkeypatch.setattr(S, "_discovered", fake)
    assert get_default_choice()["id"] == "alpha"


def test_default_none_when_no_models(monkeypatch):
    monkeypatch.setattr(S, "_discovered", [])
    assert get_default_choice() is None


# ── get_model() fallback for unknown ids (no real model load) ──────────────

def test_get_model_unknown_id_falls_back_to_default():
    default = get_default_choice()
    S._model_cache.clear()
    try:
        with patch.object(S, "MaskablePPO") as MP:
            MP.load.return_value = object()
            _, choice = S.get_model("totally_nonexistent_model_xyz")
        assert choice["id"] == default["id"]
    finally:
        S._model_cache.clear()


# ── /api/models default field ──────────────────────────────────────────────

def test_api_models_default_matches_and_is_real():
    data = client.get("/api/models").json()
    assert data["default"] == get_default_choice()["id"]
    ids = {m["id"] for m in data["models"]}
    assert data["default"] in ids
