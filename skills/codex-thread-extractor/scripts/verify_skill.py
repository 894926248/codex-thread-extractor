from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "scripts" / "extract_codex_thread.py"
TESTS = ROOT / "scripts" / "test_extract_codex_thread.py"


def find_quick_validate() -> Path:
    candidates = [
        ROOT.parent / ".system" / "skill-creator" / "scripts" / "quick_validate.py",
        Path.home() / ".codex" / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("Could not find skill-creator quick_validate.py")


def run(label: str, command: list[str]) -> None:
    print(f"== {label}")
    subprocess.run(command, check=True)


def main() -> int:
    quick_validate = find_quick_validate()
    run("skill metadata", [sys.executable, str(quick_validate), str(ROOT)])
    run("compile", [sys.executable, "-m", "py_compile", str(EXTRACTOR), str(TESTS)])
    run("tests", [sys.executable, str(TESTS)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
