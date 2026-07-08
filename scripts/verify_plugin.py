from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "codex-thread-extractor"
VALIDATE_PLUGIN = (
    Path.home()
    / ".codex"
    / "skills"
    / ".system"
    / "plugin-creator"
    / "scripts"
    / "validate_plugin.py"
)
VERIFY_SKILL = SKILL / "scripts" / "verify_skill.py"
JSON_FILES = [
    ROOT / ".codex-plugin" / "plugin.json",
]


def run(label: str, command: list[str]) -> None:
    print(f"== {label}")
    subprocess.run(command, check=True)


def validate_json_files() -> None:
    for path in JSON_FILES:
        json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not VALIDATE_PLUGIN.exists():
        raise SystemExit(f"Missing plugin validator: {VALIDATE_PLUGIN}")
    validate_json_files()
    run("plugin manifest", [sys.executable, str(VALIDATE_PLUGIN), str(ROOT)])
    run("skill", [sys.executable, str(VERIFY_SKILL)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
