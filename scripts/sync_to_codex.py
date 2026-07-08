from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "codex-thread-extractor"
DEST = Path.home() / ".codex" / "skills" / "codex-thread-extractor"


def ignore(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        or name.endswith((".pyc", ".pyo"))
    }


def main() -> int:
    if not (SOURCE / "SKILL.md").exists():
        raise SystemExit(f"Missing source skill: {SOURCE}")
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SOURCE, DEST, ignore=ignore)
    print(f"Synced {SOURCE} -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
