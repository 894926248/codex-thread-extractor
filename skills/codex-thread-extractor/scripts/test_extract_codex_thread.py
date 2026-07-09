from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("extract_codex_thread.py")
THREAD_ID = "11111111-2222-3333-4444-555555555555"
OTHER_THREAD_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def write_fixture(codex_home: Path) -> None:
    sessions = codex_home / "sessions" / "2026" / "07" / "09"
    sessions.mkdir(parents=True)
    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": THREAD_ID,
                        "thread_name": "fixture resume thread",
                        "updated_at": "2026-07-09T00:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": OTHER_THREAD_ID,
                        "thread_name": "older unrelated thread",
                        "updated_at": "2026-07-08T00:00:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    records = [
        {"type": "session_meta", "payload": {"id": THREAD_ID, "cwd": "C:/work"}},
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:01Z",
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Please continue the build."}]},
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:01Z",
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions for C:/work\ninjected project rules"}]},
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:02Z",
            "payload": {
                "type": "function_call",
                "name": "functions.shell_command",
                "call_id": "call_1",
                "arguments": json.dumps({"command": "git status --short"}),
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:03Z",
            "payload": {"type": "function_call_output", "call_id": "call_1", "output": " M file.txt"},
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:03Z",
            "payload": {
                "type": "function_call",
                "name": "read_memory",
                "call_id": "call_2",
                "arguments": json.dumps({"uri": "system://boot/brief"}),
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:03Z",
            "payload": {"type": "function_call_output", "call_id": "call_2", "output": json.dumps({"result": "boot brief"})},
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:03Z",
            "payload": {
                "type": "custom_tool_call",
                "name": "apply_patch",
                "call_id": "call_3",
                "input": "*** Begin Patch\n*** Add File: sample.txt\n+hello\n*** End Patch\n",
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:03Z",
            "payload": {"type": "custom_tool_call_output", "call_id": "call_3", "output": "Success. Updated the following files:\nA sample.txt"},
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:04Z",
            "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Next: inspect the dirty file. Unicode marker ❯"}]},
        },
    ]
    session_path = sessions / f"rollout-test-{THREAD_ID}.jsonl"
    session_path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")


def write_find_ranking_fixture(codex_home: Path) -> None:
    sessions = codex_home / "sessions" / "2026" / "07" / "09"
    sessions.mkdir(parents=True)
    raw_thread_id = "11111111-1111-1111-1111-111111111111"
    delegated_thread_id = "22222222-2222-2222-2222-222222222222"
    meta_thread_id = "33333333-3333-3333-3333-333333333333"
    quoted_thread_id = "44444444-4444-4444-4444-444444444444"
    query = "资料页 打开后 第一次 加载 慢"
    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": raw_thread_id,
                        "thread_name": "raw prompt thread",
                        "updated_at": "2026-07-09T00:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": delegated_thread_id,
                        "thread_name": "delegated prompt thread",
                        "updated_at": "2026-07-09T00:10:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": meta_thread_id,
                        "thread_name": "meta audit thread",
                        "updated_at": "2026-07-09T00:20:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": quoted_thread_id,
                        "thread_name": "quoted audit thread",
                        "updated_at": "2026-07-09T00:30:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    raw_records = [
        {"type": "session_meta", "payload": {"id": raw_thread_id, "cwd": "C:/work"}},
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:00:01Z",
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": query}]},
        },
    ]
    delegated_records = [
        {"type": "session_meta", "payload": {"id": delegated_thread_id, "cwd": "C:/work"}},
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:10:01Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": (
                    "<codex_delegation>\n"
                    "  <source_thread_id>99999999-8888-7777-6666-555555555555</source_thread_id>\n"
                    f"  <input>{query}</input>\n"
                    "</codex_delegation>"
                ),
            },
        },
    ]
    meta_records = [
        {"type": "session_meta", "payload": {"id": meta_thread_id, "cwd": "C:/work"}},
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:20:01Z",
            "payload": {
                "type": "function_call",
                "name": "create_thread",
                "call_id": "call_meta",
                "arguments": json.dumps({"prompt": query}),
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:20:02Z",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_meta",
                "output": json.dumps({"thread": {"preview": query}}, ensure_ascii=False),
            },
        },
    ]
    quoted_records = [
        {"type": "session_meta", "payload": {"id": quoted_thread_id, "cwd": "C:/work"}},
        {
            "type": "response_item",
            "timestamp": "2026-07-09T00:30:01Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Codex Desktop 线程工具验证问题报告：使用 create_thread 验证自然任务时，"
                            f"原始 prompt“{query}”被包进 delegation。这个线程只是审计，不是目标线程。"
                        ),
                    }
                ],
            },
        },
    ]
    (sessions / f"rollout-test-{raw_thread_id}.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in raw_records) + "\n",
        encoding="utf-8",
    )
    (sessions / f"rollout-test-{delegated_thread_id}.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in delegated_records) + "\n",
        encoding="utf-8",
    )
    (sessions / f"rollout-test-{meta_thread_id}.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in meta_records) + "\n",
        encoding="utf-8",
    )
    (sessions / f"rollout-test-{quoted_thread_id}.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in quoted_records) + "\n",
        encoding="utf-8",
    )


class ExtractCodexThreadTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_full_resume_and_recovery_outputs_from_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            out_dir = root / "out"
            write_fixture(codex_home)

            result = self.run_script(
                THREAD_ID,
                "--codex-home",
                str(codex_home),
                "--out-dir",
                str(out_dir),
                "--with-tools",
                "--resume-brief",
                "--recovery",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["message_count"], 8)
            self.assertEqual(summary["diagnostics"]["skipped_injected_context_count"], 1)
            for key in ("json_path", "markdown_path", "recovery_json_path", "resume_brief_json_path"):
                self.assertTrue(Path(summary[key]).exists(), key)

            brief = json.loads(Path(summary["resume_brief_json_path"]).read_text(encoding="utf-8"))
            calls = [item["command"] for item in brief["recent_tool_calls"]]
            self.assertIn("git status --short", calls)
            self.assertTrue(any("read_memory" in item and "system://boot/brief" in item for item in calls), calls)
            self.assertTrue(any("apply_patch" in item and "sample.txt" in item for item in calls), calls)
            self.assertTrue(any("Success. Updated" in item["text"] for item in brief["recent_tool_outputs"]))
            self.assertIn("Do not read the full old thread first.", brief["resume_protocol"])
            self.assertTrue(
                any("do not follow memory URIs" in item for item in brief["resume_protocol"]),
                brief["resume_protocol"],
            )

    def test_brief_only_requires_brief_or_recovery_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            write_fixture(codex_home)

            result = self.run_script(THREAD_ID, "--codex-home", str(codex_home), "--brief-only")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--brief-only requires --resume-brief or --recovery", result.stderr)

    def test_find_index_and_line_range_stay_compact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            out_dir = root / "out"
            write_fixture(codex_home)

            find_result = self.run_script("--codex-home", str(codex_home), "--find", "fixture")

            self.assertEqual(find_result.returncode, 0, find_result.stderr)
            matches = json.loads(find_result.stdout)
            self.assertEqual([item["thread_id"] for item in matches], [THREAD_ID])
            self.assertIn("title", matches[0]["matched_fields"])

            content_find_result = self.run_script("--codex-home", str(codex_home), "--find", "continue build")

            self.assertEqual(content_find_result.returncode, 0, content_find_result.stderr)
            content_matches = json.loads(content_find_result.stdout)
            self.assertEqual([item["thread_id"] for item in content_matches], [THREAD_ID])
            self.assertIn("content", content_matches[0]["matched_fields"])
            self.assertTrue(content_matches[0]["snippets"])

            output_find_result = self.run_script("--codex-home", str(codex_home), "--find", "M file.txt")

            self.assertEqual(output_find_result.returncode, 0, output_find_result.stderr)
            output_matches = json.loads(output_find_result.stdout)
            self.assertEqual([item["thread_id"] for item in output_matches], [THREAD_ID])
            self.assertIn("content", output_matches[0]["matched_fields"])

            unicode_find_result = self.run_script("--codex-home", str(codex_home), "--find", "Unicode marker")

            self.assertEqual(unicode_find_result.returncode, 0, unicode_find_result.stderr)
            unicode_matches = json.loads(unicode_find_result.stdout)
            self.assertEqual([item["thread_id"] for item in unicode_matches], [THREAD_ID])

            index_result = self.run_script(
                THREAD_ID,
                "--codex-home",
                str(codex_home),
                "--out-dir",
                str(out_dir),
                "--with-tools",
                "--index",
                "--from-line",
                "2",
                "--to-line",
                "6",
            )

            self.assertEqual(index_result.returncode, 0, index_result.stderr)
            summary = json.loads(index_result.stdout)
            self.assertLessEqual(summary["message_count"], 4)
            payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["diagnostics"]["selected_lines"], 5)
            self.assertTrue(all(item["line"] <= 6 for item in payload["messages"]))

    def test_find_prefers_real_thread_hits_over_meta_tool_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            write_find_ranking_fixture(codex_home)

            result = self.run_script(
                "--codex-home",
                str(codex_home),
                "--find",
                "资料页 打开后 第一次 加载 慢",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            matches = json.loads(result.stdout)
            self.assertEqual(
                [item["thread_name"] for item in matches[:4]],
                ["raw prompt thread", "delegated prompt thread", "quoted audit thread", "meta audit thread"],
            )
            self.assertEqual(matches[0]["snippets"][0]["kind"], "message")
            self.assertEqual(matches[0]["snippets"][0]["role"], "user")
            self.assertFalse(matches[0]["snippets"][0]["codex_delegation"])
            self.assertTrue(matches[1]["snippets"][0]["codex_delegation"])
            self.assertEqual(matches[2]["snippets"][0]["kind"], "message")
            self.assertIn(matches[3]["snippets"][0]["kind"], {"function_call", "function_call_output"})

    def test_corrupt_line_is_reported_and_parsed_records_survive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            out_dir = root / "out"
            write_fixture(codex_home)
            session_path = next((codex_home / "sessions").rglob(f"*{THREAD_ID}*.jsonl"))
            session_path.write_text(
                session_path.read_text(encoding="utf-8") + "{not-json\n",
                encoding="utf-8",
            )

            result = self.run_script(
                THREAD_ID,
                "--codex-home",
                str(codex_home),
                "--out-dir",
                str(out_dir),
                "--with-tools",
                "--resume-brief",
                "--brief-only",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["diagnostics"]["json_decode_error_count"], 1)
            self.assertTrue(Path(summary["resume_brief_json_path"]).exists())

    def test_codex_delegation_wrapper_is_diagnosed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex-home"
            out_dir = root / "out"
            write_fixture(codex_home)
            session_path = next((codex_home / "sessions").rglob(f"*{THREAD_ID}*.jsonl"))
            delegated_prompt = (
                "<codex_delegation>\n"
                "  <source_thread_id>99999999-8888-7777-6666-555555555555</source_thread_id>\n"
                "  <input>Natural request only.</input>\n"
                "</codex_delegation>"
            )
            session_path.write_text(
                session_path.read_text(encoding="utf-8")
                + json.dumps(
                    {
                        "type": "response_item",
                        "timestamp": "2026-07-09T00:00:05Z",
                        "payload": {"type": "message", "role": "user", "content": delegated_prompt},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.run_script(
                THREAD_ID,
                "--codex-home",
                str(codex_home),
                "--out-dir",
                str(out_dir),
                "--resume-brief",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["diagnostics"]["codex_delegation_count"], 1)
            self.assertEqual(summary["diagnostics"]["codex_delegation_lines"], [11])
            self.assertEqual(
                summary["diagnostics"]["codex_delegation_source_thread_ids"],
                ["99999999-8888-7777-6666-555555555555"],
            )
            payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
            delegated = [item for item in payload["messages"] if item.get("codex_delegation")]
            self.assertEqual(delegated[0]["delegation_input"], "Natural request only.")
            brief = json.loads(Path(summary["resume_brief_json_path"]).read_text(encoding="utf-8"))
            self.assertTrue(any("pure natural-prompt validation" in item for item in brief["resume_protocol"]))


if __name__ == "__main__":
    unittest.main()
