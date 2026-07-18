#!/usr/bin/env python3
"""Digest a Claude Code JSONL transcript into a compact JSON summary.

Usage:
    digest.py <transcript.jsonl>       write digest JSON to stdout
    digest.py --selftest               run assertions against fixtures
    digest.py --debug <transcript.jsonl>  digest + unknown-type counts to stderr
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ERROR_RE = re.compile(r"\bError\b|\berror:\b|Traceback|FAILED")
COMPACT_PHRASES = (
    "conversation was summarized",
    "continued from a previous conversation",
    "summary of the conversation",
)


def _text_of(content):
    """Join all text blocks of a message.content (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
        return "".join(parts)
    return ""


def _result_text(content):
    """Flatten a tool_result's content (str or list of blocks) to text for length/signal checks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text" and b.get("text"):
                    parts.append(b["text"])
            elif isinstance(b, str):
                parts.append(b)
        return "".join(parts)
    return ""


def _tool_summary(name, inp):
    inp = inp or {}
    if name == "Bash":
        return inp.get("command", "")
    if name == "Read":
        return inp.get("file_path", "")
    if name in ("Write", "Edit"):
        fp = inp.get("file_path", "")
        content = inp.get("content") or inp.get("new_string") or ""
        return f"{fp} ({len(content)} chars)"
    if name in ("Task", "Agent"):
        desc = inp.get("description", "")
        prompt = (inp.get("prompt") or "")[:120]
        return f"{desc} {prompt}".strip()
    if name == "ExitPlanMode":
        return inp.get("plan", "")
    if name == "TodoWrite":
        todos = inp.get("todos") or []
        return "; ".join(
            f"[{t.get('status', '?')}] {t.get('content', '')}"
            for t in todos if isinstance(t, dict)
        )
    try:
        s = json.dumps(inp, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(inp)
    return s[:150]


def digest(path, debug=False):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    type_counts = {}
    events = []
    session_id = None
    ai_title = None
    slug_fallback = None
    first_user_text = None
    session_date = None
    compacted = False
    compact_boundary_line = None
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    first_ts = None
    last_ts = None
    saw_valid_record = False
    unknown_type_counts = {}

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue
        if not isinstance(rec, dict):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue

        rtype = rec.get("type")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

        if session_id is None and rec.get("sessionId"):
            session_id = rec["sessionId"]

        ts = rec.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            if session_date is None:
                session_date = ts

        if rtype == "ai-title":
            for field in ("aiTitle", "title", "content"):
                val = rec.get(field)
                if isinstance(val, str) and val.strip():
                    ai_title = val.strip()
                    break

        if slug_fallback is None and isinstance(rec.get("slug"), str) and rec["slug"].strip():
            slug_fallback = rec["slug"].strip()

        # compact detection: structured markers
        if rec.get("isCompactSummary") is True:
            if not compacted:
                compacted = True
                compact_boundary_line = i
        if rtype == "summary" and (
            "compact" in json.dumps(rec, ensure_ascii=False).lower()
        ):
            if not compacted:
                compacted = True
                compact_boundary_line = i
        subtype = rec.get("subtype")
        if isinstance(subtype, str) and "compact" in subtype.lower():
            if not compacted:
                compacted = True
                compact_boundary_line = i

        if rec.get("isSidechain") is True:
            type_counts["sidechain"] = type_counts.get("sidechain", 0) + 1
            continue

        if rtype not in ("user", "assistant"):
            if rtype not in ("ai-title",):
                unknown_type_counts[rtype] = unknown_type_counts.get(rtype, 0) + 1
            continue

        message = rec.get("message")
        if not isinstance(message, dict):
            continue
        saw_valid_record = True
        content = message.get("content")

        if rtype == "user":
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    rtext = _result_text(b.get("content"))
                    is_error = b.get("is_error") is True or bool(ERROR_RE.search(rtext))
                    events.append({
                        "i": i,
                        "type": "tool_result",
                        "tool_use_id": b.get("tool_use_id", ""),
                        "chars": len(rtext),
                        "signal": "error" if is_error else "ok",
                    })
            else:
                utext = _text_of(content)
                if first_user_text is None and utext:
                    first_user_text = utext
                events.append({
                    "i": i,
                    "type": "user",
                    "ts": rec.get("timestamp", ""),
                    "uuid": rec.get("uuid", ""),
                    "text": utext,
                })
                if any(p in utext.lower() for p in COMPACT_PHRASES):
                    if not compacted:
                        compacted = True
                        compact_boundary_line = i

        elif rtype == "assistant":
            atext = _text_of(content)
            thinking_preview = ""
            tool_uses = []
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    btype = b.get("type")
                    if btype == "thinking":
                        th = b.get("thinking", "") or ""
                        if th:
                            preview = th[:200]
                            thinking_preview = f"{preview}…[{len(th)} chars]"
                    elif btype == "tool_use":
                        tool_uses.append({
                            "id": b.get("id", ""),
                            "name": b.get("name", ""),
                            "summary": _tool_summary(b.get("name", ""), b.get("input")),
                        })
            ev = {
                "i": i,
                "type": "assistant",
                "ts": rec.get("timestamp", ""),
                "uuid": rec.get("uuid", ""),
                "text": atext,
            }
            if thinking_preview:
                ev["thinking_preview"] = thinking_preview
            ev["tool_uses"] = tool_uses
            events.append(ev)

            usage = message.get("usage")
            if isinstance(usage, dict):
                for k in usage_totals:
                    v = usage.get(k)
                    if isinstance(v, (int, float)):
                        usage_totals[k] += v
            if atext and any(p in atext.lower() for p in COMPACT_PHRASES):
                if not compacted:
                    compacted = True
                    compact_boundary_line = i

    if not saw_valid_record:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(bukan format Claude Code JSONL — harness lain belum didukung)\n"
        )
        sys.exit(2)

    if ai_title:
        session_name = ai_title
    elif slug_fallback:
        session_name = slug_fallback.replace("-", " ").title()
    elif first_user_text:
        session_name = first_user_text[:80]
    else:
        session_name = "(untitled)"

    if session_id is None:
        session_id = Path(path).stem

    if debug and unknown_type_counts:
        sys.stderr.write("Unknown/unprocessed type counts:\n")
        for k, v in sorted(unknown_type_counts.items(), key=lambda kv: -kv[1]):
            sys.stderr.write(f"  {k!r}: {v}\n")

    return {
        "session_id": session_id,
        "session_name": session_name,
        "session_date": session_date,
        "compacted": compacted,
        "compact_boundary_line": compact_boundary_line,
        "transcript_meta": {
            "line_count": len(lines),
            "byte_size": os.path.getsize(path),
            "sha256_prefix": hashlib.sha256(raw).hexdigest()[:12],
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
        },
        "usage_totals": usage_totals,
        "type_counts": type_counts,
        "events": events,
    }


def _selftest():
    fixtures_dir = Path(__file__).parent.parent / "test-transcripts"
    cases = {
        "bad": "3f7a2b1c-",
        "mid": "7c1e9f3a-",
        "good": "9e4b7d2f-",
    }
    ok = True
    for name, prefix in cases.items():
        path = fixtures_dir / f"{name}.jsonl"
        try:
            d = digest(str(path))
            expected_lines = sum(1 for _ in open(path, "rb"))
            assert d["session_id"].startswith(prefix), (
                f"{name}: session_id {d['session_id']!r} does not start with {prefix!r}"
            )
            assert d["transcript_meta"]["line_count"] == expected_lines, (
                f"{name}: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
            )
            assert d["events"], f"{name}: events is empty"
            assert d["session_name"], f"{name}: session_name is empty"
            print(f"PASS {name}.jsonl")
        except Exception as e:  # noqa: BLE001 - selftest wants to catch and report everything
            ok = False
            print(f"FAIL {name}.jsonl: {e}")

    path = fixtures_dir / "compacted.jsonl"
    try:
        d = digest(str(path))
        expected_lines = sum(1 for _ in open(path, "rb"))
        assert d["transcript_meta"]["line_count"] == expected_lines, (
            f"compacted: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
        )
        assert d["events"], "compacted: events is empty"
        assert d["session_name"], "compacted: session_name is empty"
        assert d["compacted"] is True, "compacted: compacted flag is not True"
        assert d["compact_boundary_line"] is not None, "compacted: compact_boundary_line is None"
        print("PASS compacted.jsonl")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL compacted.jsonl: {e}")

    return ok


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        ok = _selftest()
        sys.exit(0 if ok else 1)

    debug = "--debug" in argv
    if debug:
        argv = [a for a in argv if a != "--debug"]

    if not argv:
        sys.stderr.write("usage: digest.py [--debug] <transcript.jsonl> | --selftest\n")
        sys.exit(2)

    d = digest(argv[0], debug=debug)
    print(json.dumps(d, ensure_ascii=False, indent=None))


if __name__ == "__main__":
    main()
