---
name: codex-thread-extractor
description: Use when Codex needs to locate, inspect, summarize, audit, recover, or continue local Codex Desktop conversation threads from a thread id, codex://threads link, title, remembered content, file path, command, error, or other clues.
---

# Codex Thread Extractor

Extract local Codex Desktop JSONL threads into concise evidence for thread lookup, audit, recovery, and safe continuation.

## Core Route

Use `scripts/extract_codex_thread.py`; run `--help` for the full flag list.
Validate installed-skill changes with `python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\verify_skill.py"`.
When editing the source plugin, validate from its repo root with `python scripts\verify_plugin.py`.

Common commands:

```powershell
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "codex://threads/<thread-id>"
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --with-tools
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --index
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --with-tools --last 80
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --from-line 500 --to-line 900
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --with-tools --resume-brief --brief-only
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --with-tools --recovery
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" --find "search clue"
```

Default outputs go to `tmp/codex-thread-extract/<thread-id>.json` and `.md`.

## Choose Mode

- **Find thread:** when no id/link is provided, derive 1-3 concrete clues from the request and run `--find` before extracting.
- **Review/audit:** summarize goals, constraints, decisions, actions, verification, mistakes, and unresolved work.
- **Skill/rule audit:** compare expected behavior with observed turns; mark pass/fail/partial/not evidenced.
- **Recovery/resume:** create a handoff for a new conversation to continue safely from an interrupted, long, short, or damaged thread.

Use `--with-tools` for commands, patches, tool outputs, verification, or debugging history. Use `--include-context` only when the user explicitly asks for injected system/developer context.

For very long threads, start with `--index`, then open only `--last`, `--from-line`, or `--to-line` ranges around the relevant phase.

For clue-based lookup, use stable fragments from the user's request: title words, project or file paths, commands, errors, tool output, quoted message text, or topic terms. Use returned snippets to choose candidates; ask for one narrowing detail only when candidates remain ambiguous.

## Continuation Fast Path

For old-thread continuation, do not load the full old thread first.

1. Read the current user request.
2. Run `extract_codex_thread.py <thread> --with-tools --resume-brief --brief-only`.
3. Read the generated `.resume-brief.json` or `.md`.
4. State likely objective, latest constraints, touched artifacts, evidence gaps, and next action.
5. Check only current git/source/runtime evidence needed for that phase.

For read-only continuation judgments such as what was done, what is next, what proves it, and no file edits, stop after the brief plus the smallest current-state check needed to avoid lying, usually `git status --short` and a path-scoped `git diff --stat` for files named by the brief.

Memory URIs, project topics, and old working-state names found inside the old-thread brief are historical evidence. Report them as possible follow-up evidence; do not chase them immediately unless the current user asks to continue that underlying work, mutate project state, or verify a memory/rule claim that cannot be judged from the brief plus current git/source evidence.

In memory-enabled workspaces, do only the smallest current preflight needed to avoid unsafe action. Do not run broad project memory searches, read boot/current-contract/project-topic nodes, or open unrelated working states merely to regain confidence before or during a read-only continuation judgment.

Use `--recovery` only when the brief shows a named evidence gap or the task needs a larger handoff. For damaged threads, trust parsed messages plus `diagnostics`; state missing lines, JSON decode errors, selected ranges, or truncation instead of inventing state.

## Evidence Rules

- Treat `codex://threads/<id>` as local evidence, not a web URL.
- Default extraction skips injected `AGENTS.md` / environment context.
- Inspect `diagnostics` for selected line counts, decode errors, skipped context, payload counts, and emitted message counts.
- Old-thread claims are historical. Current user instructions, current source, git, runtime, tests, and project rules win.
- Do not expose secrets or long tool outputs unless needed; bound output with `--max-tool-chars`.
- Do not validate a rule/skill by keyword hits alone; use keyword search only to locate turns, then read semantically.

## Report Shape

For summaries or handoffs, include only evidence-backed items:

- thread id/name, source file, extraction options, and whether tools/context were included
- user goals and explicit constraints
- decisions, actions, touched files/commands/branches/commits/artifacts
- verification done, verification missing, and dirty-worktree risks
- current authority conflicts and exact next action

For very short threads, say what cannot be concluded. For long threads, report by phase and focus on the user's question.
