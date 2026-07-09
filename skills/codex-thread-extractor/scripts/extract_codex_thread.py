from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


THREAD_RE = re.compile(
    r"(?:codex://threads/)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
TAG_TEMPLATE = r"<{tag}\b[^>]*>(.*?)</{tag}>"


@dataclass
class ThreadIndexEntry:
    thread_id: str
    thread_name: str | None
    updated_at: str | None


@dataclass
class ThreadSearchResult:
    thread_id: str
    thread_name: str | None
    updated_at: str | None
    source_file: str | None
    matched_fields: list[str]
    snippets: list[dict[str, Any]]


def default_codex_home() -> Path:
    return Path.home() / ".codex"


def normalize_thread_id(value: str) -> str:
    match = THREAD_RE.search(value.strip())
    if not match:
        raise SystemExit(f"Could not parse Codex thread id from: {value}")
    return match.group(1).lower()


def load_index(codex_home: Path) -> list[ThreadIndexEntry]:
    index_path = codex_home / "session_index.jsonl"
    if not index_path.exists():
        return []

    entries: list[ThreadIndexEntry] = []
    with index_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            thread_id = str(payload.get("id") or "").strip().lower()
            if not thread_id:
                continue
            entries.append(
                ThreadIndexEntry(
                    thread_id=thread_id,
                    thread_name=payload.get("thread_name"),
                    updated_at=payload.get("updated_at"),
                )
            )
    return entries


def find_by_index(entries: list[ThreadIndexEntry], query: str, limit: int) -> list[ThreadIndexEntry]:
    needle = query.casefold()
    matches = [
        entry
        for entry in entries
        if needle in (entry.thread_name or "").casefold() or needle in entry.thread_id.casefold()
    ]
    return sorted(matches, key=lambda item: item.updated_at or "", reverse=True)[:limit]


def query_matches(text: str, query: str) -> bool:
    haystack = text.casefold()
    needle = query.casefold().strip()
    if not needle:
        return False
    if needle in haystack:
        return True
    terms = [term for term in re.split(r"\s+", needle) if term]
    return bool(terms) and all(term in haystack for term in terms)


def iter_session_files(codex_home: Path) -> list[Path]:
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)


def thread_id_from_session_file(path: Path) -> str | None:
    match = THREAD_RE.search(path.name)
    if match:
        return match.group(1).lower()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(10):
                line = next(handle, "")
                if not line:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                thread_id = str(payload.get("id") or "").strip().lower()
                if THREAD_RE.fullmatch(thread_id):
                    return thread_id
    except OSError:
        return None
    return None


def searchable_record_snippet(record: dict[str, Any]) -> dict[str, Any] | None:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    payload_type = payload.get("type")
    if payload_type == "message":
        text = extract_text_from_content(payload.get("content"))
        if looks_like_injected_context(text):
            return None
        delegation = parse_codex_delegation(text) if text else None
        return {
            "kind": "message",
            "role": payload.get("role"),
            "text": text,
            "codex_delegation": bool(delegation),
            "delegation_input": delegation.get("input") if delegation else None,
        }
    if payload_type in {"function_call", "custom_tool_call"}:
        arguments = payload.get("input") if payload_type == "custom_tool_call" else payload.get("arguments")
        text = summarize_tool_call(payload.get("name"), arguments, max_chars=1200)
        if "extract_codex_thread.py" in text and "--find" in text:
            return None
        return {
            "kind": payload_type,
            "role": "tool_call",
            "name": payload.get("name"),
            "text": text,
            "codex_delegation": False,
        }
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        output = payload.get("output")
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "kind": payload_type,
            "role": "tool_output",
            "text": preview_text(text, 1200),
            "codex_delegation": False,
        }
    return None


def snippet_match_weight(snippet: dict[str, Any]) -> int:
    kind = snippet.get("kind")
    if kind == "message":
        role = snippet.get("role")
        if role == "user":
            return 120 if not snippet.get("codex_delegation") else 95
        if role == "assistant":
            return 90
        return 75
    if kind in {"function_call_output", "custom_tool_call_output"}:
        return 30
    if kind in {"function_call", "custom_tool_call"}:
        return 15
    return 10


def snippet_compactness_bonus(snippet: dict[str, Any], query: str) -> int:
    body = str(snippet.get("delegation_input") or snippet.get("text") or "")
    compact = re.sub(r"\s+", " ", body).strip()
    needle = re.sub(r"\s+", " ", query).strip()
    if not compact or not needle:
        return 0
    compact_folded = compact.casefold()
    needle_folded = needle.casefold()
    if needle_folded in compact_folded:
        ratio = len(needle) / max(len(compact), 1)
        if ratio >= 0.85:
            return 80
        if ratio >= 0.55:
            return 55
        if ratio >= 0.35:
            return 35
        if ratio >= 0.20:
            return 15
        return 0
    terms = [term for term in re.split(r"\s+", needle_folded) if term]
    if terms and all(term in compact_folded for term in terms) and len(compact) <= len(needle) * 3:
        return 10
    return 0


def snippet_meta_penalty(snippet: dict[str, Any]) -> int:
    if snippet.get("kind") != "message" or snippet.get("codex_delegation"):
        return 0
    body = re.sub(r"\s+", " ", str(snippet.get("text") or "")).casefold()
    penalty = 0
    if "<codex_delegation>" in body or "source_thread_id" in body:
        penalty += 25
    if "create_thread" in body or "spawn_agent" in body or "read_thread" in body or "list_threads" in body:
        penalty += 15
    if "问题报告" in body or "audit" in body or "验证" in body:
        penalty += 10
    return penalty


def search_result_score(result: ThreadSearchResult) -> tuple[int, str]:
    score = 0
    if "id" in result.matched_fields:
        score += 1000
    if "title" in result.matched_fields:
        score += 300
    snippet_scores = [max(0, int(snippet.get("match_score", 0)) - index * 5) for index, snippet in enumerate(result.snippets)]
    if snippet_scores:
        score += max(snippet_scores)
        score += sum(min(5, max(0, item - 40) // 10) for item in snippet_scores[1:])
    return score, result.updated_at or ""


def find_threads(codex_home: Path, entries: list[ThreadIndexEntry], query: str, limit: int) -> list[ThreadSearchResult]:
    by_id = {entry.thread_id: entry for entry in entries}
    results: dict[str, ThreadSearchResult] = {}

    for entry in find_by_index(entries, query, limit):
        fields = []
        if query_matches(entry.thread_id, query):
            fields.append("id")
        if query_matches(entry.thread_name or "", query):
            fields.append("title")
        results[entry.thread_id] = ThreadSearchResult(
            thread_id=entry.thread_id,
            thread_name=entry.thread_name,
            updated_at=entry.updated_at,
            source_file=None,
            matched_fields=fields or ["title"],
            snippets=[],
        )

    for path in iter_session_files(codex_home):
        thread_id = thread_id_from_session_file(path)
        if not thread_id:
            continue
        entry = by_id.get(thread_id)
        result = results.get(thread_id)
        if not result:
            result = ThreadSearchResult(
                thread_id=thread_id,
                thread_name=entry.thread_name if entry else None,
                updated_at=entry.updated_at if entry else None,
                source_file=str(path),
                matched_fields=[],
                snippets=[],
            )

        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if len(result.snippets) >= 3:
                        break
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    snippet = searchable_record_snippet(record)
                    if not snippet:
                        continue
                    text = str(snippet.get("text") or "")
                    if not text or not query_matches(text, query):
                        continue
                    if "content" not in result.matched_fields:
                        result.matched_fields.append("content")
                    match_score = (
                        snippet_match_weight(snippet)
                        + snippet_compactness_bonus(snippet, query)
                        - snippet_meta_penalty(snippet)
                    )
                    result.snippets.append(
                        {
                            "line": line_no,
                            "text": preview_text(text, 260),
                            "kind": snippet.get("kind"),
                            "role": snippet.get("role"),
                            "codex_delegation": bool(snippet.get("codex_delegation")),
                            "match_score": match_score,
                        }
                    )
        except OSError:
            continue

        if result.matched_fields:
            if not result.source_file:
                result.source_file = str(path)
            results[thread_id] = result
            if len(results) >= limit and all(item.snippets or "content" not in item.matched_fields for item in results.values()):
                break

    ordered = sorted(results.values(), key=search_result_score, reverse=True)
    return ordered[:limit]


def find_session_file(codex_home: Path, thread_id: str) -> Path:
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        raise SystemExit(f"Missing Codex sessions directory: {sessions_dir}")

    filename_matches = sorted(sessions_dir.rglob(f"*{thread_id}*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if filename_matches:
        return filename_matches[0]

    for path in sorted(sessions_dir.rglob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                first_lines = [next(handle, "") for _ in range(5)]
        except OSError:
            continue
        if thread_id in "".join(first_lines).lower():
            return path

    raise SystemExit(f"Could not find local JSONL session for thread id: {thread_id}")


def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        for key in ("text", "input_text", "output_text"):
            value = item.get(key)
            if isinstance(value, str):
                parts.append(value)
                break
        else:
            item_type = item.get("type")
            if item_type:
                parts.append(f"[{item_type}]")
    return "\n".join(part for part in parts if part).strip()


def truncate(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[:max_chars] + f"\n...[truncated {len(value) - max_chars} chars]"


def preview_text(value: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "..."


def summarize_tool_call(name: Any, arguments: Any, max_chars: int = 500) -> str:
    tool_name = str(name or "tool")
    if isinstance(arguments, str):
        arg_text = arguments
    else:
        arg_text = json.dumps(arguments, ensure_ascii=False)
    return preview_text(f"{tool_name} {arg_text}".strip(), max_chars)


def looks_like_injected_context(text: str) -> bool:
    stripped = text.lstrip()
    return (
        stripped.startswith("# AGENTS.md instructions for")
        or stripped.startswith("<environment_context>")
        or stripped.startswith("<INSTRUCTIONS>")
        or stripped.startswith("<permissions instructions>")
        or stripped.startswith("<app-context>")
        or stripped.startswith("<skills_instructions>")
        or stripped.startswith("<model_switch>")
    )


def parse_codex_delegation(text: str) -> dict[str, str] | None:
    stripped = text.strip()
    if not re.match(r"^<codex_delegation\b", stripped, re.IGNORECASE):
        return None

    def tag_value(tag: str) -> str:
        match = re.search(TAG_TEMPLATE.format(tag=re.escape(tag)), stripped, re.IGNORECASE | re.DOTALL)
        return html.unescape(match.group(1).strip()) if match else ""

    return {
        "source_thread_id": tag_value("source_thread_id"),
        "input": tag_value("input"),
    }


def parse_session(
    path: Path,
    include_tools: bool,
    include_context: bool,
    max_tool_chars: int,
    from_line: int | None = None,
    to_line: int | None = None,
    last: int | None = None,
    index_only: bool = False,
    preview_chars: int = 180,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "total_lines": 0,
        "selected_lines": 0,
        "json_decode_error_count": 0,
        "json_decode_error_lines_sample": [],
        "record_type_counts": {},
        "payload_type_counts": {},
        "skipped_injected_context_count": 0,
        "codex_delegation_count": 0,
        "codex_delegation_lines": [],
        "codex_delegation_source_thread_ids": [],
    }

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            diagnostics["total_lines"] = line_no
            if from_line is not None and line_no < from_line:
                continue
            if to_line is not None and line_no > to_line:
                continue
            diagnostics["selected_lines"] += 1
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                diagnostics["json_decode_error_count"] += 1
                if len(diagnostics["json_decode_error_lines_sample"]) < 20:
                    diagnostics["json_decode_error_lines_sample"].append(line_no)
                continue

            timestamp = record.get("timestamp")
            record_type = record.get("type")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            diagnostics["record_type_counts"][record_type or "unknown"] = (
                diagnostics["record_type_counts"].get(record_type or "unknown", 0) + 1
            )

            if record_type == "session_meta":
                metadata = {
                    "id": payload.get("id"),
                    "timestamp": payload.get("timestamp"),
                    "cwd": payload.get("cwd"),
                    "originator": payload.get("originator"),
                    "cli_version": payload.get("cli_version"),
                    "model_provider": payload.get("model_provider"),
                }
                continue

            if record_type != "response_item":
                continue

            payload_type = payload.get("type")
            diagnostics["payload_type_counts"][payload_type or "unknown"] = (
                diagnostics["payload_type_counts"].get(payload_type or "unknown", 0) + 1
            )
            if payload_type == "message":
                role = payload.get("role")
                if not include_context and role not in {"user", "assistant"}:
                    continue
                text = extract_text_from_content(payload.get("content"))
                if not include_context and looks_like_injected_context(text):
                    diagnostics["skipped_injected_context_count"] += 1
                    continue
                if text:
                    delegation = parse_codex_delegation(text)
                    if delegation:
                        diagnostics["codex_delegation_count"] += 1
                        diagnostics["codex_delegation_lines"].append(line_no)
                        source_thread_id = delegation.get("source_thread_id")
                        if source_thread_id and source_thread_id not in diagnostics["codex_delegation_source_thread_ids"]:
                            diagnostics["codex_delegation_source_thread_ids"].append(source_thread_id)
                    emitted_text = preview_text(text, preview_chars) if index_only else text
                    message = {
                        "kind": "message",
                        "role": role,
                        "text": emitted_text,
                        "timestamp": timestamp,
                        "line": line_no,
                        "chars": len(text),
                    }
                    if delegation:
                        message.update(
                            {
                                "codex_delegation": True,
                                "delegation_source_thread_id": delegation.get("source_thread_id"),
                                "delegation_input": delegation.get("input"),
                            }
                        )
                    messages.append(message)
                continue

            if include_tools and payload_type in {
                "function_call",
                "function_call_output",
                "custom_tool_call",
                "custom_tool_call_output",
            }:
                if payload_type in {"function_call", "custom_tool_call"}:
                    arguments = payload.get("arguments")
                    command = None
                    if payload_type == "custom_tool_call":
                        arguments = payload.get("input")
                    if isinstance(arguments, str):
                        try:
                            parsed_arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            parsed_arguments = {}
                        if isinstance(parsed_arguments, dict) and isinstance(parsed_arguments.get("command"), str):
                            command = parsed_arguments["command"]
                    if not command:
                        command = summarize_tool_call(payload.get("name"), arguments)
                    text = json.dumps(
                        {
                            "name": payload.get("name"),
                            "arguments": arguments,
                            "call_id": payload.get("call_id"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    role = "tool_call"
                else:
                    command = None
                    output = payload.get("output")
                    text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
                    text = truncate(text, max_tool_chars)
                    role = "tool_output"
                item = {
                    "kind": payload_type,
                    "role": role,
                    "text": preview_text(text, preview_chars) if index_only else text,
                    "timestamp": timestamp,
                    "line": line_no,
                    "chars": len(text),
                }
                if command:
                    item["command"] = command
                if payload.get("name"):
                    item["name"] = payload.get("name")
                if payload.get("call_id"):
                    item["call_id"] = payload.get("call_id")
                messages.append(item)

    if last is not None and last >= 0:
        messages = messages[-last:] if last else []

    diagnostics["emitted_message_count"] = len(messages)
    return metadata, messages, diagnostics


PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\s\"'`<>|]+|/[^\s\"'`<>|]+|(?:[\w.-]+/)+[\w.-]+)",
)


def compact_item(message: dict[str, Any], max_chars: int = 900) -> dict[str, Any]:
    item = {
        "kind": message.get("kind"),
        "role": message.get("role"),
        "timestamp": message.get("timestamp"),
        "line": message.get("line"),
        "chars": message.get("chars", len(message.get("text") or "")),
        "text": preview_text(message.get("text") or "", max_chars),
    }
    for key in ("name", "command", "call_id", "codex_delegation", "delegation_source_thread_id", "delegation_input"):
        if message.get(key):
            item[key] = message[key]
    return item


def make_recovery_packet(
    payload: dict[str, Any],
    max_tools: int = 40,
    max_outputs: int = 8,
    max_markers: int = 20,
    max_paths: int = 40,
    text_chars: int = 360,
) -> dict[str, Any]:
    messages = payload["messages"]
    user_messages = [item for item in messages if item.get("role") == "user"]
    assistant_messages = [item for item in messages if item.get("role") == "assistant"]
    tool_calls = [item for item in messages if item.get("role") == "tool_call"]
    tool_outputs = [item for item in messages if item.get("role") == "tool_output"]

    text_blob = "\n".join(item.get("text") or "" for item in messages)
    mentioned_paths = sorted(set(PATH_RE.findall(text_blob)))[:120]

    recovery_markers = []
    marker_re = re.compile(
        r"handoff|summary|继续|next|下一步|done|complete|完成|已|verification|验证|test|build|blocked|阻塞|turn_aborted|interrupted|中断|dirty|git status|git diff|git log|git show|commit|未提交|staged|剩余|下一轮|接着|恢复",
        re.IGNORECASE,
    )
    for item in messages:
        if marker_re.search(item.get("text") or "") or marker_re.search(item.get("command") or ""):
            recovery_markers.append(compact_item(item, text_chars))

    command_items = []
    for item in tool_calls:
        command = item.get("command")
        if not command:
            continue
        command_items.append(
            {
                "line": item.get("line"),
                "timestamp": item.get("timestamp"),
                "command": preview_text(command, text_chars),
            }
        )

    user_timeline = [compact_item(item, min(text_chars, 360)) for item in user_messages]
    tool_call_timeline = [
        {
            "line": item.get("line"),
            "timestamp": item.get("timestamp"),
            "command": preview_text(item.get("command") or "", min(text_chars, 300)),
        }
        for item in tool_calls
        if item.get("command")
    ]

    return {
        "purpose": "Use this packet to resume work in a new conversation without loading the full thread.",
        "thread": payload["thread"],
        "options": payload.get("options"),
        "diagnostics": payload.get("diagnostics"),
        "first_user_messages": [compact_item(item, text_chars) for item in user_messages[:5]],
        "latest_user_messages": [compact_item(item, text_chars) for item in user_messages[-8:]],
        "user_timeline": user_timeline,
        "latest_assistant_messages": [compact_item(item, text_chars) for item in assistant_messages[-8:]],
        "tool_call_timeline": tool_call_timeline[-max_tools:],
        "recent_tool_calls": command_items[-min(max_tools, 40):],
        "recent_tool_outputs": [compact_item(item, text_chars) for item in tool_outputs[-max_outputs:]],
        "recovery_markers": recovery_markers[-max_markers:],
        "mentioned_paths": mentioned_paths[:max_paths],
        "recovery_limits": {
            "max_tools": max_tools,
            "max_outputs": max_outputs,
            "max_markers": max_markers,
            "max_paths": max_paths,
            "text_chars": text_chars,
            "total_user_messages": len(user_messages),
            "total_tool_calls": len(tool_calls),
            "total_tool_outputs": len(tool_outputs),
            "total_recovery_markers": len(recovery_markers),
            "total_mentioned_paths": len(mentioned_paths),
        },
        "resume_checklist": [
            "Read current project rules before mutating state.",
            "Verify current git status and diff before trusting old-thread claims.",
            "Treat extracted thread evidence as historical; current source/runtime evidence wins.",
            "Use latest explicit user constraint over earlier plans.",
            "Do not assume completed work without current verification evidence.",
            "If diagnostics show decode errors or selected ranges, state what may be missing.",
        ],
    }


def make_resume_brief(payload: dict[str, Any]) -> dict[str, Any]:
    recovery = make_recovery_packet(
        payload,
        max_tools=16,
        max_outputs=4,
        max_markers=10,
        max_paths=24,
        text_chars=240,
    )
    return {
        "purpose": "Small first-read brief for continuing work. Read this before opening full thread extracts.",
        "thread": recovery["thread"],
        "diagnostics": recovery["diagnostics"],
        "first_user_messages": recovery["first_user_messages"][:3],
        "latest_user_messages": recovery["latest_user_messages"],
        "latest_assistant_messages": recovery["latest_assistant_messages"][-5:],
        "recent_tool_calls": recovery["recent_tool_calls"][-12:],
        "recent_tool_outputs": recovery["recent_tool_outputs"][-4:],
        "recovery_markers": recovery["recovery_markers"][-10:],
        "mentioned_paths": recovery["mentioned_paths"][:24],
        "coverage": recovery["recovery_limits"],
        "resume_protocol": [
            "Do not read the full old thread first.",
            "Read the current conversation request and current repository rules/state first.",
            "If diagnostics.codex_delegation_count > 0, do not use this trace as pure natural-prompt validation; the model saw delegation metadata.",
            "Use this brief to identify the likely objective, latest constraints, touched files, and evidence gaps.",
            "Run current git/source/runtime checks before acting on old-thread claims.",
            "For read-only continuation judgments, do not follow memory URIs or project-topic hints found in this old-thread brief; report them as possible follow-up evidence instead.",
            "Open full extract or line ranges only for a named evidence gap.",
            "If diagnostics show corruption or selected ranges, state what old-thread evidence may be missing.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    thread = payload["thread"]
    lines = [
        f"# Codex Thread Extract: {thread.get('thread_name') or thread.get('id')}",
        "",
        f"- id: `{thread.get('id')}`",
        f"- source: `{thread.get('source_file')}`",
        f"- updated_at: `{thread.get('updated_at') or ''}`",
        f"- extracted_at: `{thread.get('extracted_at')}`",
        f"- message_count: `{len(payload['messages'])}`",
        "",
    ]

    for index, message in enumerate(payload["messages"], start=1):
        role = message.get("role") or "unknown"
        timestamp = message.get("timestamp") or ""
        lines.extend(
            [
                f"## {index}. {role} `{timestamp}`",
                "",
                message.get("text") or "",
                "",
            ]
        )

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_recovery_markdown(path: Path, recovery: dict[str, Any]) -> None:
    thread = recovery["thread"]
    lines = [
        f"# Codex Thread Recovery Packet: {thread.get('thread_name') or thread.get('id')}",
        "",
        f"- source: `{thread.get('source_file')}`",
        f"- diagnostics: `{json.dumps(recovery.get('diagnostics'), ensure_ascii=False)}`",
        "",
        "## Latest User Messages",
        "",
    ]
    lines.insert(-2, "## First User Messages")
    lines.insert(-2, "")
    for item in recovery["first_user_messages"]:
        lines.insert(-2, f"- line `{item.get('line')}`: {item.get('text')}")
        lines.insert(-2, "")

    for item in recovery["latest_user_messages"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## User Timeline", ""])
    for item in recovery["user_timeline"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Latest Assistant Messages", ""])
    for item in recovery["latest_assistant_messages"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Recent Tool Calls", ""])
    for item in recovery["recent_tool_calls"]:
        lines.extend([f"- line `{item.get('line')}`: `{item.get('command')}`", ""])

    lines.extend(["## Tool Call Timeline", ""])
    for item in recovery["tool_call_timeline"]:
        lines.extend([f"- line `{item.get('line')}`: `{item.get('command')}`", ""])

    lines.extend(["## Recent Tool Outputs", ""])
    for item in recovery["recent_tool_outputs"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Recovery Markers", ""])
    for item in recovery["recovery_markers"]:
        lines.extend([f"- line `{item.get('line')}` {item.get('role')}: {item.get('text')}", ""])

    lines.extend(["## Mentioned Paths", ""])
    for path_value in recovery["mentioned_paths"]:
        lines.append(f"- `{path_value}`")

    lines.extend(["", "## Resume Checklist", ""])
    for item in recovery["resume_checklist"]:
        lines.append(f"- {item}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_resume_brief_markdown(path: Path, brief: dict[str, Any]) -> None:
    thread = brief["thread"]
    lines = [
        f"# Codex Thread Resume Brief: {thread.get('thread_name') or thread.get('id')}",
        "",
        f"- source: `{thread.get('source_file')}`",
        f"- diagnostics: `{json.dumps(brief.get('diagnostics'), ensure_ascii=False)}`",
        "",
        "## First User Signals",
        "",
    ]
    for item in brief["first_user_messages"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Latest User Signals", ""])
    for item in brief["latest_user_messages"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Latest Assistant State", ""])
    for item in brief["latest_assistant_messages"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Recent Tool Calls", ""])
    for item in brief["recent_tool_calls"]:
        lines.extend([f"- line `{item.get('line')}`: `{item.get('command')}`", ""])

    lines.extend(["## Recent Tool Outputs", ""])
    for item in brief["recent_tool_outputs"]:
        lines.extend([f"- line `{item.get('line')}`: {item.get('text')}", ""])

    lines.extend(["## Evidence Gaps And Markers", ""])
    for item in brief["recovery_markers"]:
        lines.extend([f"- line `{item.get('line')}` {item.get('role')}: {item.get('text')}", ""])

    lines.extend(["## Mentioned Paths", ""])
    for path_value in brief["mentioned_paths"]:
        lines.append(f"- `{path_value}`")

    lines.extend(["", "## Resume Protocol", ""])
    for item in brief["resume_protocol"]:
        lines.append(f"- {item}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace, thread_id: str, entry: ThreadIndexEntry | None, source_file: Path) -> dict[str, Any]:
    metadata, messages, diagnostics = parse_session(
        source_file,
        include_tools=args.with_tools,
        include_context=args.include_context,
        max_tool_chars=args.max_tool_chars,
        from_line=args.from_line,
        to_line=args.to_line,
        last=args.last,
        index_only=args.index,
        preview_chars=args.preview_chars,
    )
    output_id = metadata.get("id") or thread_id
    return {
        "thread": {
            "id": output_id,
            "thread_name": entry.thread_name if entry else None,
            "updated_at": entry.updated_at if entry else None,
            "source_file": str(source_file),
            "cwd": metadata.get("cwd"),
            "model_provider": metadata.get("model_provider"),
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
            "with_tools": bool(args.with_tools),
            "include_context": bool(args.include_context),
        },
        "options": {
            "from_line": args.from_line,
            "to_line": args.to_line,
            "last": args.last,
            "max_tool_chars": args.max_tool_chars,
            "index": bool(args.index),
            "preview_chars": args.preview_chars,
        },
        "diagnostics": diagnostics,
        "messages": messages,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Extract local Codex Desktop JSONL threads.")
    parser.add_argument("thread", nargs="?", help="codex://threads/<id> or bare thread id")
    parser.add_argument("--find", help="Search threads by title, id, or message/tool content clues")
    parser.add_argument("--limit", type=int, default=10, help="Maximum --find results")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Codex home directory")
    parser.add_argument("--out-dir", default=str(Path.cwd() / "tmp" / "codex-thread-extract"), help="Output directory")
    parser.add_argument("--with-tools", action="store_true", help="Include function/tool calls and outputs")
    parser.add_argument("--include-context", action="store_true", help="Include system/developer context messages")
    parser.add_argument("--max-tool-chars", type=int, default=4000, help="Maximum chars per tool output, 0 disables truncation")
    parser.add_argument("--from-line", type=int, help="Only extract records at or after this JSONL line number")
    parser.add_argument("--to-line", type=int, help="Only extract records at or before this JSONL line number")
    parser.add_argument("--last", type=int, help="Only keep the last N extracted messages/items after filtering")
    parser.add_argument("--index", action="store_true", help="Emit compact per-message/tool previews for timeline mapping")
    parser.add_argument("--preview-chars", type=int, default=180, help="Maximum chars per item when --index is used")
    parser.add_argument("--recovery", action="store_true", help="Also write a compact recovery packet for resuming broken or long threads")
    parser.add_argument("--resume-brief", action="store_true", help="Also write a small first-read brief for continuing work without loading the full old thread")
    parser.add_argument("--brief-only", action="store_true", help="With --resume-brief or --recovery, skip writing full extract JSON/Markdown")
    parser.add_argument("--recovery-max-tools", type=int, default=40, help="Maximum tool calls in the recovery packet")
    parser.add_argument("--recovery-max-outputs", type=int, default=8, help="Maximum tool outputs in the recovery packet")
    parser.add_argument("--recovery-max-markers", type=int, default=20, help="Maximum recovery marker items in the recovery packet")
    parser.add_argument("--recovery-max-paths", type=int, default=40, help="Maximum mentioned paths in the recovery packet")
    parser.add_argument("--recovery-text-chars", type=int, default=360, help="Maximum chars per recovery text snippet")
    args = parser.parse_args()
    if args.brief_only and not (args.resume_brief or args.recovery):
        parser.error("--brief-only requires --resume-brief or --recovery")

    codex_home = Path(args.codex_home).expanduser()
    entries = load_index(codex_home)

    if args.find:
        matches = find_threads(codex_home, entries, args.find, args.limit)
        print(json.dumps([entry.__dict__ for entry in matches], ensure_ascii=False, indent=2))
        return 0

    if not args.thread:
        parser.error("provide a thread id, codex://threads/<id>, or --find query")

    thread_id = normalize_thread_id(args.thread)
    entry = next((item for item in entries if item.thread_id == thread_id), None)
    source_file = find_session_file(codex_home, thread_id)
    payload = build_payload(args, thread_id, entry, source_file)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = None
    md_path = None
    if not args.brief_only:
        json_path = out_dir / f"{thread_id}.json"
        md_path = out_dir / f"{thread_id}.md"
        write_json(json_path, payload)
        write_markdown(md_path, payload)
    recovery_json_path = None
    recovery_md_path = None
    resume_brief_json_path = None
    resume_brief_md_path = None
    if args.recovery:
        recovery = make_recovery_packet(
            payload,
            max_tools=args.recovery_max_tools,
            max_outputs=args.recovery_max_outputs,
            max_markers=args.recovery_max_markers,
            max_paths=args.recovery_max_paths,
            text_chars=args.recovery_text_chars,
        )
        recovery_json_path = out_dir / f"{thread_id}.recovery.json"
        recovery_md_path = out_dir / f"{thread_id}.recovery.md"
        write_json(recovery_json_path, recovery)
        write_recovery_markdown(recovery_md_path, recovery)
    if args.resume_brief:
        brief = make_resume_brief(payload)
        resume_brief_json_path = out_dir / f"{thread_id}.resume-brief.json"
        resume_brief_md_path = out_dir / f"{thread_id}.resume-brief.md"
        write_json(resume_brief_json_path, brief)
        write_resume_brief_markdown(resume_brief_md_path, brief)

    print(
        json.dumps(
            {
                "thread_id": thread_id,
                "thread_name": payload["thread"].get("thread_name"),
                "source_file": str(source_file),
                "json_path": str(json_path) if json_path else None,
                "markdown_path": str(md_path) if md_path else None,
                "recovery_json_path": str(recovery_json_path) if recovery_json_path else None,
                "recovery_markdown_path": str(recovery_md_path) if recovery_md_path else None,
                "resume_brief_json_path": str(resume_brief_json_path) if resume_brief_json_path else None,
                "resume_brief_markdown_path": str(resume_brief_md_path) if resume_brief_md_path else None,
                "message_count": len(payload["messages"]),
                "with_tools": bool(args.with_tools),
                "diagnostics": payload["diagnostics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
