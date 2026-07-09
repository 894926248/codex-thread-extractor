# Release Notes

## v1.0.2 - Narrow Thread Activation

### Fixed

- Narrows automatic activation to explicit old Codex thread/history requests.
- Clarifies that files, commands, errors, rules, memory, and topic words are
  search clues only after the user asks to inspect old thread history.
- Adds validation so the skill description cannot reintroduce broad non-thread
  triggers.

### Verification

- `python scripts\verify_plugin.py`

## v1.0.1 - Delegated Trace Detection

### Fixed

- Detects `codex_delegation` user-message wrappers and records delegation
  diagnostics.
- Clarifies that delegated traces are not valid evidence for pure natural
  prompt validation.

### Verification

- `python scripts\verify_plugin.py`

## v1.0.0 - Initial Public Release

Initial open-source release of Codex Thread Extractor for Codex Desktop.

### Included

- Portable `codex-thread-extractor` skill payload.
- Local Codex thread extraction from JSONL session files.
- Markdown and JSON extraction output.
- Compact index mode for long conversations.
- Resume brief and recovery packet modes for continuing interrupted, long,
  short, or damaged threads.
- Diagnostics for selected lines, skipped injected context, JSON decode errors,
  payload counts, and emitted messages.
- Clue-based lookup when the user gives a title, remembered content, file path,
  command, error, or topic instead of a thread id.
- Codex plugin metadata validated with the local Codex plugin validator.
- Public user README and development documentation.

### Verification

- `python scripts\verify_plugin.py`
- Codex plugin manifest validation passed.
- Skill metadata validation passed.
- Python compilation passed.
- Extractor test suite passed: 4 tests.
