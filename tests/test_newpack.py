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


def test_scaffolded_pack_loads_and_is_listed():
    """Integration: scaffold into the real packs dir, load it, then clean up."""
    key = "scafftest"
    packs_dir = Path(N.__file__).resolve().parent / "packs"
    dest = packs_dir / key
    shutil.rmtree(dest, ignore_errors=True)
    try:
        N.scaffold_pack(key, name="the Test tradition", title="TestBench")
        reset_pack_cache()
        p = load_pack(key)
        assert p.key == key
        assert p.name == "the Test tradition"
        assert p.report_title == "TestBench"
        # a fresh pack namespaces all of its outputs by key
        assert p.data_dir == f"data/{key}"
        assert p.results_dir == f"results/{key}"
        assert p.reports_dir == f"reports/{key}"
        # it has a complete, loadable taxonomy + judge + authoring + review
        assert p.mc_dimensions and p.judge_dimensions and p.mc_dims and p.reviewers
        names = list_packs()
        assert key in names
        assert "_template" not in names        # scaffolding source is not selectable
    finally:
        shutil.rmtree(dest, ignore_errors=True)
        reset_pack_cache()
