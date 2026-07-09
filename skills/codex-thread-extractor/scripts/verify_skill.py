from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "scripts" / "extract_codex_thread.py"
TESTS = ROOT / "scripts" / "test_extract_codex_thread.py"
SKILL_MD = ROOT / "SKILL.md"


def find_readme() -> Path | None:
    candidates = [
        Path.cwd() / "README.md",
        ROOT.parents[1] / "README.md",
    ]
    for path in candidates:
        try:
            if path.exists() and path.is_file():
                return path
        except OSError:
            continue
    return None


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


def validate_activation_boundary() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    description = next((line for line in frontmatter.splitlines() if line.startswith("description:")), "")
    broad_triggers = ("file path", "command", "error", "other clues")
    found = [trigger for trigger in broad_triggers if trigger in description.casefold()]
    if found:
        raise SystemExit(f"Description has broad non-thread triggers: {', '.join(found)}")
    required = [
        "## Activation Gate",
        "## Route By Need",
        "Do not use it for ordinary project work",
        "become clues only after the user has asked",
        "Recent status only:",
        "Continue work:",
        "Long or damaged thread:",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f"Missing activation boundary text: {', '.join(missing)}")


def validate_readme_route_notes() -> None:
    readme = find_readme()
    if readme is None:
        return
    text = readme.read_text(encoding="utf-8")
    required = [
        "Quick recent-status check: prefer native `read_thread`.",
        "Resume/continue old work without loading the whole thread: prefer `--resume-brief --brief-only`.",
        "Long/damaged thread recovery: add `--recovery`, then `--index` or line ranges only where needed.",
        "Clue-based thread lookup: use `--find`; ranking prefers direct user/delegation hits over audit and tool-meta mentions of the same clue.",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f"Missing README route text: {', '.join(missing)}")


def main() -> int:
    quick_validate = find_quick_validate()
    run("skill metadata", [sys.executable, str(quick_validate), str(ROOT)])
    validate_activation_boundary()
    validate_readme_route_notes()
    run("compile", [sys.executable, "-m", "py_compile", str(EXTRACTOR), str(TESTS)])
    run("tests", [sys.executable, str(TESTS)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
