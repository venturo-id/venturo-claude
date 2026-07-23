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

# Case-insensitive failure signal. Real Go test failures print "FAIL" (not
# "FAILED"); "panic:" and "Traceback" cover Go/Python crashes. See P0 #8.
ERROR_RE = re.compile(r"(?i)\b(FAIL(ED)?|ERROR|Traceback|panic:)\b")
# Bash tricks that suppress a non-zero exit so a broken test/build looks green.
SUPPRESS_RE = re.compile(r"\|\|\s*true|;\s*exit\s+0|--no-verify")
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

    subagents = _read_subagents_dir(path)

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
                    is_error = b.get("is_error") is True or bool(ERROR_RE.search(rtext))
                    tuid = b.get("tool_use_id", "")
                    ev = {
                        "i": i,
                        "type": "tool_result",
                        "tool_use_id": tuid,
                        "chars": len(rtext),
                        "signal": "error" if is_error else "ok",
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
            if len(tool_uses) >= 2:
                parallel_turns += 1
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
