---
name: codex-thread-extractor
description: Use when the user explicitly asks to inspect, summarize, audit, recover, continue, or find a prior Codex Desktop conversation/thread, or provides a codex://threads link or thread id.
---

# Codex Thread Extractor

Extract local Codex Desktop JSONL threads into concise evidence for thread lookup, audit, recovery, and safe continuation.

## Activation Gate

Use this skill only when the current request clearly asks for old Codex thread evidence: a `codex://threads/<id>` link, thread id, previous/prior/old conversation, thread recovery, thread continuation, or thread/skill/rule audit.

Do not use it for ordinary project work, debugging, planning, rules, memory, files, commands, errors, or performance issues merely because those words could be search clues. File paths, commands, errors, titles, and topic words become clues only after the user has asked to find or inspect old Codex thread history.

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

- **Find thread:** when old-thread intent is explicit but no id/link is provided, derive 1-3 concrete clues from the request and run `--find` before extracting.
- **Review/audit:** summarize goals, constraints, decisions, actions, verification, mistakes, and unresolved work.
- **Skill/rule audit:** compare expected behavior with observed turns; mark pass/fail/partial/not evidenced.
- **Recovery/resume:** create a handoff for a new conversation to continue safely from an interrupted, long, short, or damaged thread.

## Route By Need

- **Recent status only:** if the user only wants what the thread was last doing, a short state summary, or a quick sanity check, prefer native `read_thread`.
- **Continue work:** if the user wants to resume work, recover next steps, identify key files/commands/verification, or avoid loading the full old thread, prefer `extract_codex_thread.py --with-tools --resume-brief --brief-only`.
- **Long or damaged thread:** if the thread is long, truncated, corrupted, or the user asks for missing-evidence risk, add `--recovery`, then `--index` or line ranges only where needed.

Use `--with-tools` for commands, patches, tool outputs, verification, or debugging history. Use `--include-context` only when the user explicitly asks for injected system/developer context.

For very long threads, start with `--index`, then open only `--last`, `--from-line`, or `--to-line` ranges around the relevant phase.

For clue-based lookup, use stable fragments from the user's request: title words, project or file paths, commands, errors, tool output, quoted message text, or topic terms. Use returned snippets to choose candidates; ask for one narrowing detail only when candidates remain ambiguous.

## Natural Prompt Validation

When auditing whether a skill/rule works on ordinary user prompts, first check `diagnostics.codex_delegation_count`.

- If it is greater than `0`, report the trace as delegated, not a pure natural-prompt run.
- Treat `<input>` as the intended prompt only; the model-visible prompt also contained delegation metadata.
- Do not use such a trace to prove automatic triggering, baseline behavior, or no-contamination behavior.
- For full-trace natural validation, use a thread created by the user/UI or another raw-prompt path that leaves no `<codex_delegation>` wrapper.

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
