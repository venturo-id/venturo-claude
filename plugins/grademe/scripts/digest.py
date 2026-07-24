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
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Case-insensitive failure signal. Real Go test failures print "FAIL" (not
# "FAILED"); "panic:" and "Traceback" cover Go/Python crashes. See P0 #8.
# NOTE: this loose substring match is intentionally kept ONLY for the
# per-event `signal` field (grader-visible "maybe worth a look" hint on
# individual tool_result events) — it is a permissive, noisy heuristic on
# purpose. It must NOT be used to compute work_evidence.error_events /
# friction_present: any tool_result text merely mentioning the word "error"
# or "fail" in prose (e.g. `git log` showing a commit message "fix error
# handling in client", or a Bash echo "no error here") would set
# error_events>=1 and thus friction_present:true, defeating both the
# no_friction→89 score cap and the synthetic-prompt exemption. See
# FRICTION_RE below for the strict, anchored rule those two fields use.
ERROR_RE = re.compile(r"(?i)\b(FAIL(ED)?|ERROR|Traceback|panic:)\b")
# Strict, anchored real-failure signal used ONLY for work_evidence.error_events
# and work_evidence.friction_present (never for the loose per-event `signal`
# field above). Every alternative is a pattern that only appears in actual
# tool/test/build failure OUTPUT, never in ordinary prose that happens to
# contain the words "error"/"fail"/"failed":
#   ^--- FAIL           Go test per-case failure marker (`go test -v`)
#   ^FAIL\b             Go test package summary line (just "FAIL" or "FAIL\t...")
#   ^FAILED             pytest verbose summary line ("FAILED tests/x.py::y")
#   ^ERROR:             anchored ERROR: at start of line (tool/build error)
#   Traceback (most...  Python traceback header
#   ^panic:             Go panic
#   exit status [1-9]   Go/bash non-zero exit status
#   exit code [1-9]     non-zero exit code
#   [1-9]\d* failed     pytest/jest/etc test-run summary ("3 failed")
#   error\[E\d+\]       rustc error code
# Case-sensitive throughout: every one of these is a fixed-case convention of
# its tool (Go/pytest/rustc), so case-insensitivity would only widen the
# surface for prose false positives without adding real coverage.
FRICTION_RE = re.compile(
    r"^--- FAIL"
    r"|^FAIL\b"
    r"|^FAILED"
    r"|^ERROR:"
    r"|Traceback \(most recent call last\)"
    r"|^panic:"
    r"|exit status [1-9]"
    r"|exit code [1-9]"
    r"|\b[1-9]\d* failed\b"
    r"|error\[E\d+\]",
    re.MULTILINE,
)
# Bash tricks that suppress a non-zero exit so a broken test/build looks green.
SUPPRESS_RE = re.compile(r"\|\|\s*true|;\s*exit\s+0|--no-verify")
# ExitPlanMode tool_result text indicating the plan was rejected, not approved.
PLAN_REJECT_RE = re.compile(r"(?i)rejected|doesn'?t want to proceed")
# mcp__<server>__<tool>
MCP_RE = re.compile(r"^mcp__(.+?)__(.+)$")
# Prose markers of a compact-continuation preamble. Honored ONLY for the very
# first user message of the transcript (see digest()) — a genuine /compact
# continuation always opens with this injected summary, whereas the same phrase
# appearing mid-session is the compact-laundering vector and is ignored. P0 #7.
COMPACT_PHRASES = (
    "conversation was summarized",
    "continued from a previous conversation",
    "summary of the conversation",
)
# Attachment record types we keep (everything else is dropped). P0 #4.
KEEP_ATTACHMENTS = (
    "skill_listing",
    "agent_listing_delta",
    "plan_mode",
    "plan_mode_exit",
    "hook_success",
    "queued_command",
)
MAX_RESULT_TEXT = 1500
MAX_USAGE_LIST = 20


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


def _head_tail(s, limit):
    """Truncate to `limit` chars keeping head + tail (subagent reports carry
    their conclusion at the end)."""
    if len(s) <= limit:
        return s
    head = limit * 2 // 3
    tail = limit - head
    return f"{s[:head]}\n…[{len(s) - limit} chars omitted]…\n{s[-tail:]}"


def _norm_dispatch(desc, prompt):
    """Normalized fingerprint for distinctness (desc + first 200 chars of prompt)."""
    s = f"{desc or ''} {(prompt or '')[:200]}"
    return re.sub(r"\s+", " ", s).strip().lower()


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
        prompt = (inp.get("prompt") or "")[:300]
        return f"{desc} {prompt}".strip()
    if name == "Skill":
        skill = inp.get("skill", "")
        args = (inp.get("args") or "")[:200]
        return f"{skill} {args}".strip()
    if name == "ExitPlanMode":
        return inp.get("plan", "")
    if name == "EnterPlanMode":
        return ""
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


def _tool_extra(name, inp):
    """Structured fields for a tool_use, beyond the human-readable summary.
    Empty dict when there is nothing extra to record."""
    inp = inp or {}
    extra = {}
    if name == "Skill":
        extra["skill"] = inp.get("skill", "")
        args = inp.get("args") or ""
        if args:
            extra["args"] = args[:200]
    elif name in ("Task", "Agent"):
        st = inp.get("subagent_type")
        if st:
            extra["subagent_type"] = st
        if "run_in_background" in inp:
            extra["run_in_background"] = bool(inp.get("run_in_background"))
    else:
        m = MCP_RE.match(name or "")
        if m:
            extra["mcp_server"] = m.group(1)
            extra["mcp_tool"] = m.group(2)
    if name == "Bash":
        cmd = inp.get("command", "") or ""
        if SUPPRESS_RE.search(cmd):
            extra["suppressed"] = True
    return extra


def _parse_tool_use_result(tur):
    """Parse a top-level toolUseResult into (kind, data).
    kind is "subagent", "skill", or None (nothing worth attaching)."""
    if not isinstance(tur, dict):
        return None, None
    if "agentType" in tur or "toolStats" in tur or "totalToolUseCount" in tur:
        data = {}
        for k in ("status", "agentType", "resolvedModel",
                  "totalToolUseCount", "totalDurationMs", "totalTokens"):
            if k in tur:
                data[k] = tur[k]
        ts = tur.get("toolStats")
        if isinstance(ts, dict):
            data["toolStats"] = {
                k: ts.get(k)
                for k in ("readCount", "bashCount", "editFileCount",
                          "linesAdded", "linesRemoved")
                if k in ts
            }
        txt = _result_text(tur.get("content"))
        if txt:
            data["result_text"] = _head_tail(txt, MAX_RESULT_TEXT)
        return "subagent", data
    if "commandName" in tur:
        data = {"commandName": tur.get("commandName")}
        if "success" in tur:
            data["success"] = tur.get("success")
        return "skill", data
    return None, None


def _read_subagents_dir(path):
    """Aggregate sidecar subagent transcripts, if present. Never inlines
    subagent message bodies — histograms + counts only. Fully guarded."""
    result = {"present": False, "agents": []}
    try:
        p = Path(path)
        subdir = p.parent / p.stem / "subagents"
        if not subdir.is_dir():
            return result
        result["present"] = True
        for meta_path in sorted(subdir.glob("agent-*.meta.json"))[:50]:
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            agent = {
                "agentType": meta.get("agentType", ""),
                "description": meta.get("description", ""),
                "toolUseId": meta.get("toolUseId", ""),
                "spawnDepth": meta.get("spawnDepth"),
            }
            jsonl_path = subdir / (meta_path.name[: -len(".meta.json")] + ".jsonl")
            hist = {}
            recs = 0
            try:
                with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        recs += 1
                        try:
                            r = json.loads(line)
                        except (ValueError, json.JSONDecodeError):
                            continue
                        m = r.get("message")
                        if isinstance(m, dict) and isinstance(m.get("content"), list):
                            for b in m["content"]:
                                if isinstance(b, dict) and b.get("type") == "tool_use":
                                    nm = b.get("name", "")
                                    hist[nm] = hist.get(nm, 0) + 1
            except OSError:
                pass
            agent["record_count"] = recs
            agent["tool_histogram"] = hist
            result["agents"].append(agent)
    except OSError:
        pass
    return result


def digest(path, debug=False):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        sys.stderr.write(
            f"ERROR: file transkrip tidak ada atau kosong: {path}\n"
        )
        sys.exit(2)
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    type_counts = {}
    events = []
    session_id = None
    cc_version = None
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
    saw_real_assistant_structure = False
    nonempty_line_count = 0
    valid_json_dict_count = 0
    cc_style_record_count = 0
    unknown_type_counts = {}

    # tool_usage / signal_availability accumulators
    skill_invocations = []          # {name, line, args}
    skill_success = {}              # commandName -> bool
    slash_commands = []             # {name, args, line}
    dispatches = []                 # {subagent_type, description, prompt, tool_use_id, run_in_background, line}
    subagent_results_by_id = {}     # tool_use_id -> parsed subagent data
    attrib_skill_turns = {}         # attributionSkill -> assistant-turn count
    mcp_counter = {}                # server -> call count
    skills_available = []           # union of skill_listing names (order-preserving, deduped)
    agent_types_available = []      # union of agent_listing_delta addedTypes
    plan_enter = 0
    plan_exit = 0
    plan_file_exists = False
    parallel_turns = 0
    main_thread_tool_calls = 0
    has_tool_use_result = False
    has_attribution = False
    has_attachments = False

    # work_evidence accumulators (Requirement A)
    error_event_lines = []          # transcript line numbers where a tool_result errored
    plan_revisions = 0
    exit_plan_mode_ids = set()       # tool_use ids of ExitPlanMode tool_use blocks
    assistant_tool_use_lines = []     # line numbers of assistant records with >=1 tool_use
    genuine_user_turns = 0            # type:"user" records that are NOT tool_result blocks
                                       # (i.e. real human input, same test used for first_user_text)

    subagents = _read_subagents_dir(path)

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        nonempty_line_count += 1
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue
        if not isinstance(rec, dict):
            type_counts["malformed"] = type_counts.get("malformed", 0) + 1
            continue
        valid_json_dict_count += 1

        rtype = rec.get("type")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

        # "record bergaya Claude Code" (Requirement D): a known CC record
        # type. Foreign JSONL harnesses (e.g. Antigravity) use different
        # top-level `type` vocabularies entirely, so this alone separates them.
        if rtype in ("user", "assistant", "system", "summary", "attachment", "ai-title"):
            cc_style_record_count += 1

        if rtype == "assistant":
            msg = rec.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                saw_real_assistant_structure = True

        if session_id is None and rec.get("sessionId"):
            session_id = rec["sessionId"]
        if cc_version is None and rec.get("version"):
            cc_version = rec["version"]
        if rec.get("toolUseResult") is not None:
            has_tool_use_result = True

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

        # compact detection: structured markers only (P0 #7).
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

        if rtype == "attachment":
            has_attachments = True
            att = rec.get("attachment")
            if isinstance(att, dict):
                atype = att.get("type")
                if atype in KEEP_ATTACHMENTS:
                    ev = {"i": i, "type": "attachment", "attachment_type": atype}
                    if atype == "skill_listing":
                        names = att.get("names") or []
                        ev["names"] = names[:80]
                        ev["skillCount"] = att.get("skillCount")
                        for n in names:
                            if n not in skills_available:
                                skills_available.append(n)
                    elif atype == "agent_listing_delta":
                        added = att.get("addedTypes") or []
                        ev["addedTypes"] = added
                        for a in added:
                            if a not in agent_types_available:
                                agent_types_available.append(a)
                    elif atype in ("plan_mode", "plan_mode_exit"):
                        ev["planFilePath"] = att.get("planFilePath", "")
                        ev["planExists"] = att.get("planExists")
                        if atype == "plan_mode":
                            plan_enter += 1
                        else:
                            plan_exit += 1
                        if att.get("planExists") is True:
                            plan_file_exists = True
                    elif atype == "hook_success":
                        ev["hookName"] = att.get("hookName", "")
                        ev["hookEvent"] = att.get("hookEvent", "")
                    # queued_command: presence only
                    events.append(ev)
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
                kind, tur_data = _parse_tool_use_result(rec.get("toolUseResult"))
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    rtext = _result_text(b.get("content"))
                    is_error_flag = b.get("is_error") is True
                    # Loose signal for grader visibility on the per-event
                    # `signal` field only — see ERROR_RE comment above.
                    is_error_loose = is_error_flag or bool(ERROR_RE.search(rtext))
                    # Strict signal for work_evidence.error_events /
                    # friction_present — anchored real-failure patterns only,
                    # so prose mentions of "error"/"fail" never count.
                    is_error_strict = is_error_flag or bool(FRICTION_RE.search(rtext))
                    tuid = b.get("tool_use_id", "")
                    if is_error_strict:
                        error_event_lines.append(i)
                    if tuid in exit_plan_mode_ids and PLAN_REJECT_RE.search(rtext):
                        plan_revisions += 1
                    ev = {
                        "i": i,
                        "type": "tool_result",
                        "tool_use_id": tuid,
                        "chars": len(rtext),
                        "signal": "error" if is_error_loose else "ok",
                    }
                    if tur_data is not None:
                        ev["result"] = tur_data
                        if kind == "subagent" and tuid:
                            subagent_results_by_id[tuid] = tur_data
                        elif kind == "skill":
                            cn = tur_data.get("commandName")
                            if cn:
                                skill_success[cn] = tur_data.get("success")
                    events.append(ev)
            else:
                genuine_user_turns += 1
                utext = _text_of(content)
                is_first_user = first_user_text is None
                if is_first_user and utext:
                    first_user_text = utext
                events.append({
                    "i": i,
                    "type": "user",
                    "ts": rec.get("timestamp", ""),
                    "uuid": rec.get("uuid", ""),
                    "text": utext,
                })
                # slash-command invocation (participant-initiated skill use)
                m = re.search(r"<command-name>([^<]+)</command-name>", utext)
                if m:
                    cargs = ""
                    ma = re.search(r"<command-args>([^<]*)</command-args>", utext)
                    if ma:
                        cargs = ma.group(1).strip()
                    slash_commands.append({"name": m.group(1).strip(), "args": cargs, "line": i})
                # prose compaction: first user message ONLY (anti-laundering, P0 #7)
                if is_first_user and any(p in utext.lower() for p in COMPACT_PHRASES):
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
                        nm = b.get("name", "")
                        inp = b.get("input")
                        tu = {
                            "id": b.get("id", ""),
                            "name": nm,
                            "summary": _tool_summary(nm, inp),
                        }
                        tu.update(_tool_extra(nm, inp))
                        tool_uses.append(tu)
                        main_thread_tool_calls += 1

                        mcpm = MCP_RE.match(nm or "")
                        if mcpm:
                            srv = mcpm.group(1)
                            mcp_counter[srv] = mcp_counter.get(srv, 0) + 1
                        if nm == "Skill":
                            si = inp or {}
                            skill_invocations.append({
                                "name": si.get("skill", ""),
                                "line": i,
                                "args": (si.get("args") or "")[:200],
                            })
                        elif nm in ("Task", "Agent"):
                            di = inp or {}
                            dispatches.append({
                                "subagent_type": di.get("subagent_type", ""),
                                "description": di.get("description", ""),
                                "prompt": di.get("prompt") or "",
                                "tool_use_id": b.get("id", ""),
                                "run_in_background": (
                                    bool(di.get("run_in_background"))
                                    if "run_in_background" in di else None
                                ),
                                "line": i,
                            })
                        elif nm == "EnterPlanMode":
                            plan_enter += 1
                        elif nm == "ExitPlanMode":
                            plan_exit += 1
                            tuid = b.get("id", "")
                            if tuid:
                                exit_plan_mode_ids.add(tuid)
            if len(tool_uses) >= 2:
                parallel_turns += 1
            if tool_uses:
                assistant_tool_use_lines.append(i)
            ev = {
                "i": i,
                "type": "assistant",
                "ts": rec.get("timestamp", ""),
                "uuid": rec.get("uuid", ""),
                "text": atext,
            }
            if thinking_preview:
                ev["thinking_preview"] = thinking_preview
            for k in ("attributionSkill", "attributionPlugin",
                      "attributionMcpServer", "attributionMcpTool"):
                v = rec.get(k)
                if v:
                    ev[k] = v
                    has_attribution = True
                    if k == "attributionSkill":
                        attrib_skill_turns[v] = attrib_skill_turns.get(v, 0) + 1
            ev["tool_uses"] = tool_uses
            events.append(ev)

            usage = message.get("usage")
            if isinstance(usage, dict):
                for k in usage_totals:
                    v = usage.get(k)
                    if isinstance(v, (int, float)):
                        usage_totals[k] += v

    if nonempty_line_count == 0 or valid_json_dict_count == 0:
        sys.stderr.write(
            "ERROR: semua baris gagal di-parse sebagai JSON (file korup atau kosong)\n"
        )
        sys.exit(2)
    if cc_style_record_count < 3:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(kurang dari 3 record bergaya Claude Code — bukan format Claude Code JSONL)\n"
        )
        sys.exit(2)
    if not saw_real_assistant_structure:
        sys.stderr.write(
            "ERROR: transcript format not recognized "
            "(tidak ada record type:\"assistant\" dengan message.content array asli Claude Code)\n"
        )
        sys.exit(2)
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

    # --- work_evidence (Requirement A) ---
    duration_minutes = 0
    if first_ts and last_ts:
        try:
            dt_first = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
            dt_last = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            duration_minutes = max(0, int((dt_last - dt_first).total_seconds() // 60))
        except (ValueError, TypeError):
            duration_minutes = 0

    error_events = len(error_event_lines)
    last_tool_use_line = max(assistant_tool_use_lines) if assistant_tool_use_lines else None
    errors_followed_up = sum(
        1 for eline in error_event_lines
        if last_tool_use_line is not None and last_tool_use_line > eline
    )
    # plan_revisions: explicit rejected ExitPlanMode tool_results are the
    # strongest signal; failing that, >1 ExitPlanMode call in one session is
    # itself evidence of at least one revision (first exit didn't stick).
    if plan_revisions == 0 and plan_exit > 1:
        plan_revisions = plan_exit - 1
    friction_present = error_events > 0 or plan_revisions > 0

    work_evidence = {
        "duration_minutes": duration_minutes,
        # genuine human turns only: type:"user" records whose message.content is
        # NOT a tool_result block. Deliberately does NOT reuse type_counts["user"]
        # (that count includes tool_result-bearing user records — autonomous
        # tool-cycle echoes — which would let a 1-prompt/N-tool-cycle "one-shot"
        # session evade the short_session gate below). assistant_turns keeps
        # reusing type_counts since there is no analogous tool-result pollution
        # for assistant records.
        "user_turns": genuine_user_turns,
        "assistant_turns": type_counts.get("assistant", 0),
        "error_events": error_events,
        "errors_followed_up": errors_followed_up,
        "plan_revisions": plan_revisions,
        "friction_present": friction_present,
    }

    # --- score_caps (Requirement B) ---
    cap_candidates = [100]
    cap_reasons = []
    if duration_minutes < 15 or work_evidence["user_turns"] < 5:
        cap_candidates.append(85)
        cap_reasons.append("short_session→85")
    if not friction_present:
        cap_candidates.append(89)
        cap_reasons.append("no_friction→89")
    score_caps = {"cap": min(cap_candidates), "reasons": cap_reasons}

    tool_usage = _build_tool_usage(
        skill_invocations, skill_success, slash_commands, dispatches,
        subagent_results_by_id, attrib_skill_turns, mcp_counter,
        skills_available, agent_types_available, plan_enter, plan_exit,
        plan_file_exists, parallel_turns, main_thread_tool_calls, subagents,
    )

    signal_availability = {
        "cc_version": cc_version,
        "has_tool_use_result": has_tool_use_result,
        "has_attribution": has_attribution,
        "has_attachments": has_attachments,
        "subagents_dir_present": subagents["present"],
    }

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
        "first_user_prompt": first_user_text,
        "transcript_meta": {
            "line_count": len(lines),
            "byte_size": os.path.getsize(path),
            "sha256_prefix": hashlib.sha256(raw).hexdigest()[:12],
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "cc_version": cc_version,
        },
        "usage_totals": usage_totals,
        "type_counts": type_counts,
        "tool_usage": tool_usage,
        "signal_availability": signal_availability,
        "work_evidence": work_evidence,
        "score_caps": score_caps,
        "events": events,
    }


def _build_tool_usage(skill_invocations, skill_success, slash_commands,
                      dispatches, subagent_results_by_id, attrib_skill_turns,
                      mcp_counter, skills_available, agent_types_available,
                      plan_enter, plan_exit, plan_file_exists, parallel_turns,
                      main_thread_tool_calls, subagents):
    # --- skills: aggregate invocations by name ---
    slash_names = {sc["name"].lstrip("/") for sc in slash_commands}
    slash_leaves = {n.split(":")[-1] for n in slash_names}
    # attribution is recorded plugin-qualified ("plugin:skill") while a Skill
    # invocation names the skill bare ("skill"); index turns by leaf too so the
    # two forms reconcile (leaf = segment after the last ':').
    attrib_by_leaf = {}
    for k, v in attrib_skill_turns.items():
        leaf = k.split(":")[-1]
        attrib_by_leaf[leaf] = attrib_by_leaf.get(leaf, 0) + v
    skills_by_name = {}
    for inv in skill_invocations:
        name = inv["name"]
        e = skills_by_name.get(name)
        if e is None:
            e = {"name": name, "invocations": 0, "first_line": inv["line"], "args": inv.get("args", "")}
            skills_by_name[name] = e
        e["invocations"] += 1
    skills_out = []
    for name, e in skills_by_name.items():
        turns = attrib_skill_turns.get(name)
        if turns is None:
            turns = attrib_by_leaf.get(name.split(":")[-1], 0)
        e["attributed_turns"] = turns
        e["user_initiated"] = (
            name in slash_names or name.split(":")[-1] in slash_leaves
        )
        # skill_success is keyed by commandName (== skill name in practice)
        succ = skill_success.get(name)
        if succ is None:
            succ = skill_success.get(name.split(":")[-1])
        e["success"] = succ
        skills_out.append(e)

    # --- subagents: join each dispatch with its returned telemetry ---
    subagents_out = []
    delegated_tool_use = 0
    for d in dispatches:
        res = subagent_results_by_id.get(d["tool_use_id"], {})
        ts = res.get("toolStats") or {}
        ttuc = res.get("totalToolUseCount")
        if isinstance(ttuc, (int, float)):
            delegated_tool_use += ttuc
        rt = res.get("result_text")
        subagents_out.append({
            "agent_type": d.get("subagent_type") or res.get("agentType", ""),
            "description": d.get("description", ""),
            "tool_use_id": d["tool_use_id"],
            "status": res.get("status"),
            "total_tool_use_count": ttuc,
            "duration_ms": res.get("totalDurationMs"),
            "tokens": res.get("totalTokens"),
            "edits": ts.get("editFileCount"),
            "lines_added": ts.get("linesAdded"),
            "result_chars": len(rt) if rt else None,
            "run_in_background": d.get("run_in_background"),
            "line": d["line"],
        })

    distinct = len({_norm_dispatch(d["description"], d["prompt"]) for d in dispatches})

    return {
        "skills": skills_out[:MAX_USAGE_LIST],
        "slash_commands": slash_commands[:MAX_USAGE_LIST],
        "subagents": subagents_out[:MAX_USAGE_LIST],
        "dispatch_totals": {
            "dispatches": len(dispatches),
            "distinct_dispatches": distinct,
            "parallel_turns": parallel_turns,
            "delegated_tool_use": delegated_tool_use,
            "main_thread_tool_use": main_thread_tool_calls,
        },
        "mcp": {"servers": mcp_counter, "total_calls": sum(mcp_counter.values())},
        "plan_mode": {
            "enter_count": plan_enter,
            "exit_count": plan_exit,
            "plan_file_exists": plan_file_exists,
        },
        "skills_available": skills_available,
        "agent_types_available": agent_types_available,
        "subagents_sidecar": subagents["agents"][:MAX_USAGE_LIST],
    }


def _run_cli_exit_code(path):
    """Invoke this script as a subprocess against `path` and return its exit
    code (selftest-only helper for hard-reject assertions, which must exercise
    the real CLI entrypoint — `main()` writes stdout only on success)."""
    proc = subprocess.run(
        [sys.executable, str(Path(__file__)), path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
    )
    return proc.returncode


def _synthetic_jsonl(records):
    """Write `records` (list of dicts) as a temp .jsonl file, return its path.
    Selftest-only helper for the synthetic work_evidence/score_caps/hard-reject
    cases (Requirement E) that don't need a checked-in fixture file."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    with fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return fh.name


def _synthetic_session(session_id, turns, extra_last=None):
    """Build a minimal but structurally-real Claude Code JSONL: alternating
    user/assistant text turns with timestamps 1 minute apart, each assistant
    turn carrying one Bash tool_use so there is something for a subsequent
    tool_result to attach to. `turns` is the number of user+assistant pairs.
    `extra_last` (list of records) is appended verbatim (e.g. an errored
    tool_result) before the session closes."""
    recs = [{"type": "system", "subtype": "info", "content": "Session started",
             "sessionId": session_id}]
    base_min = 0
    for n in range(turns):
        ts_u = f"2026-07-01T09:{base_min:02d}:00.000Z"
        base_min += 1
        ts_a = f"2026-07-01T09:{base_min:02d}:00.000Z"
        base_min += 1
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": f"turn {n} instruksi"},
            "uuid": f"{session_id}-u{n}", "timestamp": ts_u, "sessionId": session_id,
        })
        recs.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"toolu_{n}", "name": "Bash",
                 "input": {"command": "go test ./..."}}
            ]},
            "uuid": f"{session_id}-a{n}", "timestamp": ts_a, "sessionId": session_id,
        })
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{n}", "content": "ok"}
            ]},
            "uuid": f"{session_id}-r{n}", "timestamp": ts_a, "sessionId": session_id,
        })
    if extra_last:
        recs.extend(extra_last)
    return recs


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
            assert "tool_usage" in d, f"{name}: tool_usage missing"
            assert "signal_availability" in d, f"{name}: signal_availability missing"
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

    # --- P3 modern-format fixtures: assert the tool_usage discriminators ---
    def _bash_suppressed(d):
        return any(
            t.get("suppressed") is True
            for e in d["events"] if e.get("type") == "assistant"
            for t in e.get("tool_uses", [])
        )

    checks = {
        # skill-real: relevant user-initiated skill WITH dwell + a consumed subagent
        "skill-real": lambda d: (
            any(s["attributed_turns"] >= 10 and s["user_initiated"] is True
                for s in d["tool_usage"]["skills"])
            and any((s["total_tool_use_count"] or 0) > 1
                    for s in d["tool_usage"]["subagents"])
            and d["tool_usage"]["dispatch_totals"]["dispatches"] >= 1
        ),
        # skill-ritual: many dispatches that all collapse to ONE fingerprint
        "skill-ritual": lambda d: (
            d["tool_usage"]["dispatch_totals"]["dispatches"] >= 12
            and d["tool_usage"]["dispatch_totals"]["distinct_dispatches"] == 1
        ),
        # gamed: suppressed test surfaces AND mid-transcript laundering is ignored
        "gamed": lambda d: (
            _bash_suppressed(d) and d["compacted"] is False
        ),
        # compacted-structured: structured marker sets the boundary regardless of position
        "compacted-structured": lambda d: (
            d["compacted"] is True and d["compact_boundary_line"] is not None
        ),
    }
    for name, ok_fn in checks.items():
        path = fixtures_dir / f"{name}.jsonl"
        try:
            d = digest(str(path))
            expected_lines = sum(1 for _ in open(path, "rb"))
            assert d["transcript_meta"]["line_count"] == expected_lines, (
                f"{name}: line_count {d['transcript_meta']['line_count']} != wc -l {expected_lines}"
            )
            assert d["events"], f"{name}: events is empty"
            assert d["session_name"], f"{name}: session_name is empty"
            assert ok_fn(d), f"{name}: tool_usage discriminator assertion failed"
            print(f"PASS {name}.jsonl")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL {name}.jsonl: {e}")

    # --- friction-forge fix: FRICTION_RE must ignore prose, catch real failures ---

    def _friction_case(name, tool_result_content, expect_error_events, expect_friction):
        """Build a 16-turn synthetic session with one extra tool_result carrying
        `tool_result_content`, and assert error_events/friction_present match
        expectations. Session is long enough (>=15min, user_turns>=5) that
        short_session does not also fire and confound the friction assertion."""
        sid = f"aaaaaaaa-0000-4000-8000-0000000000{name}"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_friction",
                 "content": tool_result_content}
            ]}, "uuid": f"{sid}-fr", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == expect_error_events, (
                f"friction case {name!r} ({tool_result_content[:50]!r}): "
                f"error_events {we['error_events']} != {expect_error_events}"
            )
            assert we["friction_present"] is expect_friction, (
                f"friction case {name!r} ({tool_result_content[:50]!r}): "
                f"friction_present {we['friction_present']} != {expect_friction}"
            )
            return True
        finally:
            os.unlink(path)

    friction_cases = [
        # (id-suffix, tool_result text, expect_error_events, expect_friction, label)
        ("a1", "abc123 fix error handling in client", 0, False, "benign: commit-message-like prose"),
        ("a2", "no error here", 0, False, "benign: plain prose mentioning error"),
        ("a3", "build failed nowhere", 0, False, "benign: prose containing 'failed' mid-sentence"),
        ("a4", "--- FAIL: TestX\nFAIL\nexit status 1", 1, True, "real: go test -v failure + summary + exit status"),
        ("a5", "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom", 1, True, "real: python traceback"),
        ("a6", "3 failed, 12 passed in 4.21s", 1, True, "real: pytest summary line"),
    ]
    for suffix, text, exp_events, exp_friction, label in friction_cases:
        try:
            _friction_case(suffix, text, exp_events, exp_friction)
            print(f"PASS friction_re: {label}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL friction_re {label}: {e}")

    # is_error:true flag alone (no matching text) must still count as strict friction.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000a07"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_flag",
                 "content": "some ordinary output", "is_error": True}
            ]}, "uuid": f"{sid}-fr", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"is_error flag: error_events {we['error_events']} != 1"
            assert we["friction_present"] is True, "is_error flag: friction_present should be True"
            print("PASS friction_re: is_error:true flag counts regardless of text")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL friction_re is_error flag: {e}")

    # --- Requirement E: work_evidence / score_caps / first_user_prompt / hard reject ---

    # work_evidence: error + follow-up. Long enough session (16 turns, ~32min,
    # user_turns well above 5) so short_session cap does NOT also fire.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000001"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_err", "content": "--- FAIL: TestX\nFAIL"}
            ]}, "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_followup", "name": "Bash",
                 "input": {"command": "go test ./... -run TestX"}}
            ]}, "uuid": f"{sid}-followup", "timestamp": "2026-07-01T09:34:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 1, f"error_events {we['error_events']} != 1"
            assert we["errors_followed_up"] == 1, f"errors_followed_up {we['errors_followed_up']} != 1"
            assert we["friction_present"] is True, "friction_present should be True with an error"
            # user_turns counts GENUINE human messages only (16, one per synthetic
            # turn) — it must NOT reuse type_counts["user"] (32: 16 real + 16
            # tool_result echoes, plus the extra errored tool_result = 33).
            assert we["user_turns"] == 16, f"user_turns {we['user_turns']} != 16 (genuine human turns)"
            assert we["user_turns"] != d["type_counts"].get("user", 0), (
                "user_turns must NOT reuse type_counts[\"user\"] (would include tool_result echoes)"
            )
            assert we["assistant_turns"] == d["type_counts"].get("assistant", 0), (
                "assistant_turns must reuse type_counts"
            )
            assert we["duration_minutes"] >= 15, f"duration_minutes {we['duration_minutes']} too short for this case"
            assert d["score_caps"]["cap"] == 100, (
                f"long session with friction should NOT be capped, got {d['score_caps']}"
            )
            print("PASS work_evidence: error + follow-up")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence error+follow-up: {e}")

    # work_evidence: clean/mulus session — no errors, no plan revisions.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000002"
        recs = _synthetic_session(sid, turns=16)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["error_events"] == 0, f"error_events {we['error_events']} != 0"
            assert we["errors_followed_up"] == 0, f"errors_followed_up {we['errors_followed_up']} != 0"
            assert we["plan_revisions"] == 0, f"plan_revisions {we['plan_revisions']} != 0"
            assert we["friction_present"] is False, "friction_present should be False for a clean session"
            print("PASS work_evidence: clean session")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence clean session: {e}")

    # work_evidence: "one-shot" gamed session — 1 real human prompt followed by
    # 20 autonomous assistant/tool_result cycles spanning >=15 minutes. Before
    # the fix, user_turns reused type_counts["user"] (21: 1 real + 20
    # tool_result echoes) and evaded the short_session gate entirely. It must
    # now count only the genuine human message, so user_turns == 1 and the
    # short_session cap fires even though duration_minutes >= 15.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000007"
        recs = [{"type": "system", "subtype": "info", "content": "Session started",
                 "sessionId": sid}]
        recs.append({
            "type": "user",
            "message": {"role": "user", "content": "tolong benerin semua test yang gagal"},
            "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid,
        })
        base_min = 1
        for n in range(20):
            ts_a = f"2026-07-01T09:{base_min:02d}:00.000Z"
            base_min += 1
            recs.append({
                "type": "assistant",
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": f"toolu_os{n}", "name": "Bash",
                     "input": {"command": "go test ./..."}}
                ]},
                "uuid": f"{sid}-a{n}", "timestamp": ts_a, "sessionId": sid,
            })
            recs.append({
                "type": "user",
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": f"toolu_os{n}", "content": "ok"}
                ]},
                "uuid": f"{sid}-r{n}", "timestamp": ts_a, "sessionId": sid,
            })
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            we = d["work_evidence"]
            assert we["duration_minutes"] >= 15, (
                f"duration_minutes {we['duration_minutes']} too short for this case"
            )
            assert we["user_turns"] == 1, (
                f"one-shot gamed session: user_turns {we['user_turns']} != 1 "
                "(must not reuse type_counts[\"user\"], which would be 21)"
            )
            assert "short_session→85" in d["score_caps"]["reasons"], (
                f"one-shot gamed session must not evade short_session gate: {d['score_caps']}"
            )
            print("PASS work_evidence: one-shot gamed session user_turns=1 → short_session gate fires")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL work_evidence one-shot gamed session: {e}")

    # score_caps: short session (< 15 min AND < 5 user turns) → cap 85.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000003"
        recs = _synthetic_session(sid, turns=2)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            sc = d["score_caps"]
            assert sc["cap"] == 85, f"short session cap {sc['cap']} != 85 ({sc})"
            assert "short_session→85" in sc["reasons"], f"missing short_session reason: {sc['reasons']}"
            print("PASS score_caps: short_session→85")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL score_caps short_session: {e}")

    # score_caps: no friction (long enough session, zero errors, zero plan
    # revisions) → cap 89.
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000004"
        recs = _synthetic_session(sid, turns=16)
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            sc = d["score_caps"]
            assert sc["cap"] == 89, f"no-friction cap {sc['cap']} != 89 ({sc})"
            assert "no_friction→89" in sc["reasons"], f"missing no_friction reason: {sc['reasons']}"
            assert "short_session→85" not in sc["reasons"], "should not also be a short session"
            print("PASS score_caps: no_friction→89")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL score_caps no_friction: {e}")

    # score_caps: long session WITH friction → cap stays 100 (no gate fires).
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000005"
        recs = _synthetic_session(sid, turns=16, extra_last=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_err2", "content": "--- FAIL: TestBoom\nFAIL"}
            ]}, "uuid": f"{sid}-err", "timestamp": "2026-07-01T09:33:00.000Z", "sessionId": sid},
        ])
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            sc = d["score_caps"]
            assert sc["cap"] == 100, f"long+friction cap {sc['cap']} != 100 ({sc})"
            assert sc["reasons"] == [], f"no gate should fire, got {sc['reasons']}"
            print("PASS score_caps: long session + friction → 100")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL score_caps long+friction: {e}")

    # first_user_prompt: verbatim, no truncation, even for a very long prompt
    # (well past session_name's 80-char cut and MAX_RESULT_TEXT's 1500).
    try:
        sid = "aaaaaaaa-0000-4000-8000-000000000006"
        long_prompt = "Konteks panjang. " * 200  # ~3400 chars
        recs = [
            {"type": "system", "subtype": "info", "content": "Session started", "sessionId": sid},
            {"type": "user", "message": {"role": "user", "content": long_prompt},
             "uuid": f"{sid}-u0", "timestamp": "2026-07-01T09:00:00.000Z", "sessionId": sid},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "ok"}]},
             "uuid": f"{sid}-a0", "timestamp": "2026-07-01T09:01:00.000Z", "sessionId": sid},
        ]
        path = _synthetic_jsonl(recs)
        try:
            d = digest(path)
            assert d["first_user_prompt"] == long_prompt, "first_user_prompt was mutated/truncated"
            assert len(d["first_user_prompt"]) == len(long_prompt), (
                f"length mismatch: {len(d['first_user_prompt'])} != {len(long_prompt)}"
            )
            assert len(d["session_name"]) <= 80, "session_name truncation must be unaffected"
            print("PASS first_user_prompt: verbatim, untruncated")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL first_user_prompt: {e}")

    # hard reject: empty file → exit non-zero, no output.
    try:
        path = _synthetic_jsonl([])
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "empty file must exit non-zero"
            print("PASS hard reject: empty file")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject empty file: {e}")

    # hard reject: corrupt JSON (every line fails to parse) → exit non-zero.
    try:
        fh = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        with fh:
            fh.write("not json\n{also not json\nstill not json\n")
        path = fh.name
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "all-corrupt file must exit non-zero"
            print("PASS hard reject: corrupt JSON")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject corrupt JSON: {e}")

    # hard reject: fewer than 3 valid Claude-Code-style records.
    try:
        recs = [
            {"type": "user", "message": {"role": "user", "content": "hi"},
             "sessionId": "x", "timestamp": "2026-07-01T09:00:00.000Z"},
        ]
        path = _synthetic_jsonl(recs)
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "fewer than 3 CC-style records must exit non-zero"
            print("PASS hard reject: fewer than 3 valid records")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject <3 records: {e}")

    # hard reject: foreign harness JSONL (Antigravity-style: different `type`
    # vocabulary, no Claude Code assistant message.content array anywhere).
    try:
        recs = [
            {"type": "agent_turn", "role": "model", "text": "hello", "turnId": 1},
            {"type": "agent_turn", "role": "model", "text": "world", "turnId": 2},
            {"type": "tool_call", "name": "read_file", "args": {"path": "x"}, "turnId": 3},
        ]
        path = _synthetic_jsonl(recs)
        try:
            rc = _run_cli_exit_code(path)
            assert rc != 0, "foreign-format transcript must exit non-zero"
            print("PASS hard reject: foreign harness format (Antigravity-style)")
        finally:
            os.unlink(path)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL hard reject foreign format: {e}")

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
