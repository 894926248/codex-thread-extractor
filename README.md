# Codex Thread Extractor

Locate, summarize, audit, and recover local Codex Desktop conversation threads.

This skill is useful when you need evidence from a prior Codex Desktop
conversation, whether you have an exact `codex://threads/<id>` link or only
partial clues.

- What happened in this conversation?
- What files, commands, decisions, and verification steps were involved?
- Did an agent follow a skill, rule, or workflow correctly?
- Can a new conversation safely continue work from an old, long, short, or
  damaged thread?

The extractor reads local Codex Desktop JSONL session files. It is not a web
service and does not upload thread contents.

## Installation

### Codex

Clone this repository:

```powershell
git clone https://github.com/894926248/codex-thread-extractor.git
cd codex-thread-extractor
```

Install the skill into your local Codex skills directory:

```powershell
python scripts\sync_to_codex.py
```

Start a new Codex conversation after installing or updating the skill.

## Usage

In Codex, the skill is intended to be selected automatically when your request
needs evidence from local Codex Desktop thread history. You can provide a
thread link/id, or just clues such as title words, file names, commands, errors,
tool output, quoted message text, or topic terms.

Examples:

```text
Summarize codex://threads/<thread-id>
Find the earlier conversation where we discussed release setup.
Recover the thread that changed the README so a new conversation can continue it.
```

You can still name the skill explicitly when you want to force that route.

Common direct script commands:

```powershell
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "codex://threads/<thread-id>"
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --with-tools --resume-brief --brief-only
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" "<thread-id>" --index
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" --find "search clue"
```

Default output is written under:

```text
tmp/codex-thread-extract/
```

Run help for all options:

```powershell
python "$env:USERPROFILE\.codex\skills\codex-thread-extractor\scripts\extract_codex_thread.py" --help
```

## What It Produces

Depending on the flags, the extractor can create:

- compact Markdown and JSON summaries
- message indexes for long threads
- recent-tool and verification-aware resume briefs
- recovery packets for continuing interrupted or damaged threads
- diagnostics for skipped injected context, JSON decode errors, selected line
  ranges, and parsed message counts

By default, injected `AGENTS.md` and environment context are skipped to reduce
noise and avoid wasting context.

## Development

Skill payload:

```text
skills/codex-thread-extractor/
```

Codex plugin metadata lives in `.codex-plugin/`.

Validate before publishing changes:

```powershell
python scripts\verify_plugin.py
```

Then sync the Codex consumer copy:

```powershell
python scripts\sync_to_codex.py
```
