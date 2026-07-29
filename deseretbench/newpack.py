"""Scaffold a new faith pack from the template.

    python -m deseretbench.newpack <key> [--name "..."] [--title "..."] [--force]

Copies deseretbench/packs/_template/ to deseretbench/packs/<key>/, substituting
the identity fields, then verifies the new pack loads. From there, fill in the
TODOs in the generated pack.py (taxonomy, judge, authoring, review) and its
grounding_brief.md. Full walkthrough: docs/how-to/add-a-faith-pack.md.

Nothing here runs a model.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

_PACKS_DIR = Path(__file__).resolve().parent / "packs"
_TEMPLATE = _PACKS_DIR / "_template"

# A pack key is a Python package name: lowercase, starts with a letter, then
# letters / digits / underscores. That keeps `import deseretbench.packs.<key>`
# working and the key usable as a directory and a path segment.
_KEY_RE = re.compile(r"[a-z][a-z0-9_]*\Z")


def _default_name(key: str) -> str:
    return f"the {key.replace('_', ' ')} tradition"


def _default_title(key: str) -> str:
    return key.replace("_", " ").title()


def scaffold_pack(key: str, name: str | None = None, title: str | None = None,
                  dest_root: Path | None = None, force: bool = False) -> Path:
    """Create packs/<key>/ from the template and return its path.

    dest_root defaults to the real packs directory; tests pass a tmp dir.
    """
    if not _KEY_RE.match(key or ""):
        raise ValueError(
            f"invalid pack key {key!r}: use lowercase letters, digits, and "
            f"underscores, starting with a letter (e.g. 'catholic', "
            f"'eastern_orthodox').")
    name = name or _default_name(key)
    title = title or _default_title(key)
    dest_root = Path(dest_root) if dest_root is not None else _PACKS_DIR
    dest = dest_root / key
    if dest.exists():
        if not force:
            raise FileExistsError(
                f"{dest} already exists; pass force=True (--force) to overwrite.")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    subs = {"__KEY__": key, "__NAME__": name, "__TITLE__": title}
    for src in sorted(_TEMPLATE.iterdir()):
        if src.name == "__pycache__" or not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        for placeholder, value in subs.items():
            text = text.replace(placeholder, value)
        (dest / src.name).write_text(text, encoding="utf-8")
    return dest


def main():
    ap = argparse.ArgumentParser(
        description="Scaffold a new DeseretBench faith pack from the template.")
    ap.add_argument("key", help="pack key: lowercase letters/digits/underscores "
                                 "(e.g. catholic, eastern_orthodox)")
    ap.add_argument("--name", default=None,
                    help='tradition, phrased to drop into a sentence '
                         '(default: "the <key> tradition")')
    ap.add_argument("--title", default=None,
                    help="report wordmark (default: the key, title-cased)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing pack of this key")
    args = ap.parse_args()

    try:
        dest = scaffold_pack(args.key, name=args.name, title=args.title,
                             force=args.force)
    except (ValueError, FileExistsError) as e:
        raise SystemExit(f"error: {e}")

    # Self-check: the fresh pack must import and construct a valid Pack.
    from .packs import load_pack, reset_pack_cache
    reset_pack_cache()
    pack = load_pack(args.key)
    rel = dest.relative_to(Path(__file__).resolve().parent.parent)

    print(f"created faith pack '{pack.key}' at {rel}/")
    print("\nNext steps:")
    print(f"  1. Fill the TODOs in {rel}/pack.py — taxonomy, judge, authoring, review.")
    print(f"  2. Write {rel}/grounding_brief.md (the factual anchor for authoring).")
    print(f"  3. Select it:  export DESERETBENCH_PACK={pack.key}   "
          f"(or set `pack: {pack.key}` in configs/run_config.yaml)")
    print(f"  4. Author -> validate -> score per docs/how-to/add-a-faith-pack.md.")
    print(f"\n  Outputs are namespaced: data/{pack.key}/, results/{pack.key}/, "
          f"reports/{pack.key}/ — the LDS set is never touched.")


if __name__ == "__main__":
    main()
