"""Tests for the faith-pack scaffolder (`python -m deseretbench.newpack`)."""

import shutil
from pathlib import Path

import pytest

import deseretbench.newpack as N
from deseretbench.packs import list_packs, load_pack, reset_pack_cache


def test_scaffold_substitutes_identity_and_stays_valid_python(tmp_path):
    dest = N.scaffold_pack("catholic", name="the Catholic tradition",
                           title="CatholicBench", dest_root=tmp_path)
    assert dest == tmp_path / "catholic"
    pack_py = (dest / "pack.py").read_text()
    for placeholder in ("__KEY__", "__NAME__", "__TITLE__"):
        assert placeholder not in pack_py
    assert 'KEY = "catholic"' in pack_py
    assert "the Catholic tradition" in pack_py
    assert "CatholicBench" in pack_py
    assert (dest / "grounding_brief.md").exists()
    assert (dest / "__init__.py").exists()
    compile(pack_py, str(dest / "pack.py"), "exec")   # generated code parses


def test_scaffold_defaults_name_and_title_from_key(tmp_path):
    dest = N.scaffold_pack("eastern_orthodox", dest_root=tmp_path)
    pack_py = (dest / "pack.py").read_text()
    assert "the eastern orthodox tradition" in pack_py   # readable default name
    assert "Eastern Orthodox" in pack_py                 # title-cased default wordmark


@pytest.mark.parametrize("bad", ["_leading", "1digit", "Capital", "has space", "hy-phen", ""])
def test_scaffold_rejects_invalid_keys(tmp_path, bad):
    with pytest.raises(ValueError):
        N.scaffold_pack(bad, dest_root=tmp_path)


def test_scaffold_refuses_existing_unless_forced(tmp_path):
    N.scaffold_pack("orthodox", dest_root=tmp_path)
    with pytest.raises(FileExistsError):
        N.scaffold_pack("orthodox", dest_root=tmp_path)
    # --force overwrites cleanly
    again = N.scaffold_pack("orthodox", dest_root=tmp_path, force=True)
    assert again.exists()


def test_newpack_defaults_to_the_external_packs_dir(tmp_path, monkeypatch):
    """No dest_root -> scaffold OUTSIDE the deseretbench package (DeseretBench is
    lds-only), honoring DESERETBENCH_PACK_PATH."""
    monkeypatch.setenv("DESERETBENCH_PACK_PATH", str(tmp_path))
    dest = N.scaffold_pack("byzantine")          # no dest_root
    assert dest == tmp_path / "byzantine"
    assert "deseretbench" not in str(dest).replace("\\", "/").rsplit("/byzantine", 1)[0]


def test_scaffolded_external_pack_loads_and_is_listed(tmp_path, monkeypatch):
    """Integration: scaffold to an external dir, load it via the search path."""
    monkeypatch.setenv("DESERETBENCH_PACK_PATH", str(tmp_path))
    N.scaffold_pack("byzantine", name="the Byzantine tradition", title="ByzBench")
    reset_pack_cache()
    p = load_pack("byzantine")
    assert p.key == "byzantine"
    assert p.name == "the Byzantine tradition"
    assert p.report_title == "ByzBench"
    # a fresh pack namespaces all of its outputs by key
    assert p.data_dir == "data/byzantine"
    assert p.results_dir == "results/byzantine"
    assert p.reports_dir == "reports/byzantine"
    # complete, loadable taxonomy + judge + authoring + review
    assert p.mc_dimensions and p.judge_dimensions and p.mc_dims and p.reviewers
    names = list_packs()
    assert "byzantine" in names            # external
    assert "lds" in names                  # in-package
    assert "_template" not in names        # scaffolding source is not selectable
    reset_pack_cache()
