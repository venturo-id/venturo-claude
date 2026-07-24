#!/usr/bin/env python3
"""Validate a grader-produced submission JSON against its source digest JSON.

Mechanical gatekeeper for v0.6.0: sits between the grader subagent (LLM,
untrusted) and downstream presentation/upload. It re-checks everything the
grader could get wrong or fake — breakdown arithmetic, score caps, and
verbatim forensic fields the digest itself computed — WITHOUT re-reading the
transcript. Exit 0 = submission accepted; exit non-zero = rejected, with one
"VALIDATION FAIL: ..." line per violation on stderr (ALL violations are
reported, not just the first).

Usage:
    validate.py --digest DIGEST.json --submission SUBMISSION.json
    validate.py --selftest
"""
import copy
import json
import os
import sys

# Weights v0.6.0 (BEKU) — total 100.
WEIGHTS = {
    "planning": 15,
    "context": 15,
    "decomposition": 15,
    "delegation": 18,
    "verification": 20,
    "token_efficiency": 12,
    "documentation": 5,
}
STRUCTURAL_CAP = 98
MIN_MISSES = 2

# Fields the submission must reproduce byte-for-byte from the digest (rule 5).
FORENSIC_FIELDS = (
    "transcript_meta",
    "usage_totals",
    "type_counts",
    "tool_usage",
    "work_evidence",
    "score_caps",
    "first_user_prompt",
    "session_id",
    "signal_availability",
)

DIGEST_INVALID_MSG = "digest invalid — jalankan ulang digest.py"

# Sentinel distinguishing "key absent" from "key present with value None" —
# both digest and submission may legitimately carry an explicit null.
_MISSING = object()


class DigestInvalid(Exception):
    """Raised when the digest file fails the sanity check (rule 7)."""


def load_digest(path):
    """Load+sanity-check a digest JSON file (rule 7). Raises DigestInvalid
    with the exact rejection message on any problem: missing file, empty
    file, invalid JSON, not-a-dict, or missing one of the three load-bearing
    keys (session_id, score_caps, work_evidence)."""
    try:
        if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
            raise DigestInvalid(DIGEST_INVALID_MSG)
    except OSError:
        raise DigestInvalid(DIGEST_INVALID_MSG)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError):
        raise DigestInvalid(DIGEST_INVALID_MSG)
    if not isinstance(data, dict):
        raise DigestInvalid(DIGEST_INVALID_MSG)
    for key in ("session_id", "score_caps", "work_evidence"):
        if key not in data:
            raise DigestInvalid(DIGEST_INVALID_MSG)
    return data


def load_submission(path):
    """Load a submission JSON file. Raises ValueError on any structural
    problem (missing file, invalid JSON, not-a-dict) — this is a distinct
    failure mode from digest sanity (rule 7 is digest-specific)."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        raise ValueError("submission tidak ada atau kosong")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"submission bukan JSON valid: {e}")
    if not isinstance(data, dict):
        raise ValueError("submission bukan objek JSON")
    return data


def _is_plain_int(v):
    """True for real ints, False for bool (bool is a subclass of int in
    Python and must never pass as a score/count)."""
    return isinstance(v, int) and not isinstance(v, bool)


def _check_breakdown(submission, violations):
    """Rule 1: breakdown fields exist, are plain ints, in [0, max], and sum
    to total_score. Returns (breakdown_ok, total_score_ok) so later rules can
    know whether total_score is trustworthy enough to compare against caps."""
    breakdown = submission.get("breakdown")
    total_score = submission.get("total_score")
    total_score_ok = _is_plain_int(total_score)
    if not total_score_ok:
        violations.append(
            f"total_score bukan integer: {total_score!r}"
        )

    if not isinstance(breakdown, dict):
        violations.append("breakdown bukan objek (dict)")
        return False, total_score_ok

    breakdown_ok = True
    running_sum = 0
    all_values_valid = True
    for dim, mx in WEIGHTS.items():
        if dim not in breakdown:
            violations.append(f"breakdown.{dim} tidak ada")
            breakdown_ok = False
            all_values_valid = False
            continue
        v = breakdown[dim]
        if not _is_plain_int(v):
            violations.append(f"breakdown.{dim} bukan integer: {v!r}")
            breakdown_ok = False
            all_values_valid = False
            continue
        if v < 0 or v > mx:
            violations.append(
                f"breakdown.{dim} di luar rentang 0..{mx}: {v}"
            )
            breakdown_ok = False
        running_sum += v

    if all_values_valid and total_score_ok:
        if running_sum != total_score:
            violations.append(
                f"jumlah breakdown ({running_sum}) != total_score ({total_score})"
            )
            breakdown_ok = False

    return breakdown_ok, total_score_ok


def _check_misses(submission, violations):
    """Rule 2: misses array with >=2 non-empty string items."""
    misses = submission.get("misses")
    if not isinstance(misses, list):
        violations.append("misses bukan array")
        return
    valid = [m for m in misses if isinstance(m, str) and m.strip()]
    if len(valid) < MIN_MISSES:
        violations.append(
            f"misses harus berisi minimal {MIN_MISSES} item non-kosong, "
            f"didapat {len(valid)}"
        )


def _check_score_caps(digest, submission, total_score_ok, violations):
    """Rule 3: total_score <= digest's score_caps.cap."""
    if not total_score_ok:
        return
    total_score = submission.get("total_score")
    score_caps = digest.get("score_caps")
    cap = score_caps.get("cap") if isinstance(score_caps, dict) else None
    if not _is_plain_int(cap):
        violations.append("digest.score_caps.cap tidak ada/tidak valid")
        return
    if total_score > cap:
        violations.append(
            f"total_score ({total_score}) melebihi score_caps.cap dari digest ({cap})"
        )


def _check_structural_cap(submission, total_score_ok, violations):
    """Rule 4: total_score <= 98 (hard structural cap, independent of digest)."""
    if not total_score_ok:
        return
    total_score = submission["total_score"]
    if total_score > STRUCTURAL_CAP:
        violations.append(
            f"total_score ({total_score}) melebihi cap struktural {STRUCTURAL_CAP}"
        )


def _check_forensic_fields(digest, submission, violations):
    """Rule 5: forensic fields must deep-equal the digest verbatim. A field
    absent/null in the digest must also be absent/null in the submission —
    it may not be invented."""
    for field in FORENSIC_FIELDS:
        digest_val = digest.get(field, _MISSING)
        digest_absent = digest_val is _MISSING or digest_val is None
        sub_val = submission.get(field, _MISSING)
        if digest_absent:
            if sub_val is not _MISSING and sub_val is not None:
                violations.append(
                    f"field forensik '{field}' dikarang — absen/null di digest "
                    f"tapi ada nilainya di submission"
                )
            continue
        if sub_val is _MISSING:
            violations.append(
                f"field forensik '{field}' tidak ada di submission (harus identik dengan digest)"
            )
            continue
        if sub_val != digest_val:
            violations.append(
                f"field forensik '{field}' tidak identik dengan digest (deep equal gagal)"
            )


def _check_anti_hand_authored(digest, submission, total_score_ok, violations):
    """Rule 6: if signal_availability shows no tool_use_result telemetry, no
    attribution, and no cc_version, the transcript is very likely
    hand-authored (not a real Claude Code session) — total_score must be
    capped at 70 regardless of what the grader claims."""
    sig = digest.get("signal_availability")
    if not isinstance(sig, dict):
        return
    suspicious = (
        sig.get("has_tool_use_result") is False
        and sig.get("has_attribution") is False
        and not sig.get("cc_version")
    )
    if not suspicious or not total_score_ok:
        return
    total_score = submission["total_score"]
    if total_score > 70:
        violations.append(
            "signal_availability menunjukkan transcript kemungkinan hand-authored "
            "(has_tool_use_result=false, has_attribution=false, cc_version kosong) — "
            f"total_score ({total_score}) harus <=70"
        )


def validate(digest, submission):
    """Run rules 1–6 against an already sanity-checked digest dict (rule 7
    is checked separately by load_digest before this is called). Returns a
    list of human-readable violation strings — empty means the submission
    passes."""
    violations = []
    _, total_score_ok = _check_breakdown(submission, violations)
    _check_misses(submission, violations)
    _check_score_caps(digest, submission, total_score_ok, violations)
    _check_structural_cap(submission, total_score_ok, violations)
    _check_forensic_fields(digest, submission, violations)
    _check_anti_hand_authored(digest, submission, total_score_ok, violations)
    return violations


# --- selftest fixtures -------------------------------------------------

def _synthetic_digest(cap=95, has_tool_use_result=True, has_attribution=True,
                       cc_version="2.1.217"):
    """A minimal but structurally complete digest dict covering every
    forensic field the validator checks."""
    return {
        "session_id": "test-session-0001",
        "session_name": "Test session",
        "session_date": "2026-07-01T09:00:00.000Z",
        "compacted": False,
        "compact_boundary_line": None,
        "first_user_prompt": "tolong tambah endpoint /healthz yang ngecek db",
        "transcript_meta": {
            "line_count": 42,
            "byte_size": 12345,
            "sha256_prefix": "abc123def456",
            "first_timestamp": "2026-07-01T09:00:00.000Z",
            "last_timestamp": "2026-07-01T10:00:00.000Z",
            "cc_version": cc_version,
        },
        "usage_totals": {
            "input_tokens": 1000,
            "output_tokens": 2000,
            "cache_read_input_tokens": 500,
        },
        "type_counts": {"system": 1, "user": 6, "assistant": 10},
        "tool_usage": {
            "skills": [],
            "slash_commands": [],
            "subagents": [],
            "dispatch_totals": {
                "dispatches": 0, "distinct_dispatches": 0,
                "parallel_turns": 0, "delegated_tool_use": 0,
                "main_thread_tool_use": 10,
            },
            "mcp": {"servers": {}, "total_calls": 0},
            "plan_mode": {"enter_count": 0, "exit_count": 1, "plan_file_exists": False},
            "skills_available": [],
            "agent_types_available": [],
            "subagents_sidecar": [],
        },
        "signal_availability": {
            "cc_version": cc_version,
            "has_tool_use_result": has_tool_use_result,
            "has_attribution": has_attribution,
            "has_attachments": False,
            "subagents_dir_present": False,
        },
        "work_evidence": {
            "duration_minutes": 30,
            "user_turns": 6,
            "assistant_turns": 10,
            "error_events": 1,
            "errors_followed_up": 1,
            "plan_revisions": 0,
            "friction_present": True,
        },
        "score_caps": {"cap": cap, "reasons": []},
        "events": [],
    }


_VALID_BREAKDOWN = {
    "planning": 12, "context": 12, "decomposition": 10,
    "delegation": 14, "verification": 15, "token_efficiency": 9,
    "documentation": 4,
}  # sums to 76


def _valid_submission_for(digest, total_score=76, breakdown=None, misses=None):
    if breakdown is None:
        breakdown = dict(_VALID_BREAKDOWN)
    if misses is None:
        misses = [
            "Tidak membaca output test sebelum menganggap perbaikan selesai",
            "Tidak ada dokumentasi/README yang diperbarui",
        ]
    sub = {"total_score": total_score, "breakdown": breakdown, "misses": misses}
    for f in FORENSIC_FIELDS:
        sub[f] = copy.deepcopy(digest.get(f))
    return sub


def _selftest():
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        if cond:
            print(f"PASS {name}")
        else:
            ok = False
            print(f"FAIL {name}: {detail}")

    # 1. Perfectly valid submission → no violations.
    d = _synthetic_digest(cap=95)
    s = _valid_submission_for(d)
    v = validate(d, s)
    check("valid submission → no violations", v == [], v)

    # 2. Rule 2 — misses has only 1 item.
    d = _synthetic_digest(cap=95)
    s = _valid_submission_for(d, misses=["Hanya satu miss di sini"])
    v = validate(d, s)
    check(
        "rule2: misses 1 item → fail",
        any("misses" in m for m in v),
        v,
    )

    # 3. Rule 4 — total_score 100 (violates structural cap 98), breakdown
    #    engineered to sum to 100 so rule 1 does NOT also fire.
    d = _synthetic_digest(cap=100)
    bd = {"planning": 15, "context": 15, "decomposition": 15, "delegation": 18,
          "verification": 20, "token_efficiency": 12, "documentation": 5}  # sums to 100
    s = _valid_submission_for(d, total_score=100, breakdown=bd)
    v = validate(d, s)
    check(
        "rule4: total_score 100 → cap struktural 98 fail",
        any("cap struktural" in m for m in v),
        v,
    )

    # 4. Rule 3 — total_score (90) exceeds digest's score_caps.cap (85).
    d = _synthetic_digest(cap=85)
    bd = {"planning": 14, "context": 14, "decomposition": 14, "delegation": 16,
          "verification": 18, "token_efficiency": 10, "documentation": 4}  # sums to 90
    s = _valid_submission_for(d, total_score=90, breakdown=bd)
    v = validate(d, s)
    check(
        "rule3: total_score 90 > digest cap 85 → fail",
        any("score_caps.cap" in m for m in v),
        v,
    )

    # 5. Rule 1a — breakdown sum mismatch (sum 76 but total_score says 80).
    d = _synthetic_digest(cap=95)
    s = _valid_submission_for(d, total_score=80)  # breakdown still sums to 76
    v = validate(d, s)
    check(
        "rule1: breakdown sum mismatch → fail",
        any("jumlah breakdown" in m for m in v),
        v,
    )

    # 6. Rule 1b — one breakdown field exceeds its own max.
    d = _synthetic_digest(cap=95)
    bd = dict(_VALID_BREAKDOWN)
    bd["documentation"] = 8  # max is 5
    s = _valid_submission_for(d, total_score=sum(bd.values()), breakdown=bd)
    v = validate(d, s)
    check(
        "rule1: breakdown field melebihi max → fail",
        any("breakdown.documentation" in m and "rentang" in m for m in v),
        v,
    )

    # 7. Rule 5 — transcript_meta mutated (one value changed from the digest).
    d = _synthetic_digest(cap=95)
    s = _valid_submission_for(d)
    s["transcript_meta"] = copy.deepcopy(s["transcript_meta"])
    s["transcript_meta"]["line_count"] += 1
    v = validate(d, s)
    check(
        "rule5: transcript_meta diubah → fail",
        any("transcript_meta" in m for m in v),
        v,
    )

    # 8. Rule 6 — signal_availability hand-authored + total_score 90 (>70).
    d = _synthetic_digest(cap=95, has_tool_use_result=False, has_attribution=False,
                          cc_version=None)
    bd = {"planning": 15, "context": 15, "decomposition": 13, "delegation": 16,
          "verification": 18, "token_efficiency": 9, "documentation": 4}  # sums to 90
    s = _valid_submission_for(d, total_score=90, breakdown=bd)
    v = validate(d, s)
    check(
        "rule6: hand-authored signals + score 90 → fail",
        any("hand-authored" in m for m in v),
        v,
    )

    # 8b. Same hand-authored signals but total_score <= 70 → rule 6 must NOT fire.
    d = _synthetic_digest(cap=95, has_tool_use_result=False, has_attribution=False,
                          cc_version=None)
    bd = {"planning": 10, "context": 10, "decomposition": 10, "delegation": 10,
          "verification": 10, "token_efficiency": 10, "documentation": 5}  # sums to 65
    s = _valid_submission_for(d, total_score=65, breakdown=bd)
    v = validate(d, s)
    check(
        "rule6: hand-authored signals + score <=70 → no rule6 violation",
        not any("hand-authored" in m for m in v),
        v,
    )

    # 9. Rule 7 — digest file missing score_caps → DigestInvalid with the
    #    exact rejection message, via the real load_digest() entrypoint.
    import tempfile
    d = _synthetic_digest(cap=95)
    del d["score_caps"]
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        raised = False
        msg = ""
        try:
            load_digest(fh.name)
        except DigestInvalid as e:
            raised = True
            msg = str(e)
        check(
            "rule7: digest tanpa score_caps → DigestInvalid",
            raised and msg == DIGEST_INVALID_MSG,
            msg,
        )
    finally:
        os.unlink(fh.name)

    # 9b. Rule 7 — digest file missing entirely → DigestInvalid.
    raised = False
    try:
        load_digest("/tmp/does-not-exist-grademe-validate-selftest.json")
    except DigestInvalid:
        raised = True
    check("rule7: digest file missing → DigestInvalid", raised)

    # 9c. Rule 7 — a well-formed, sane digest loads without raising.
    d = _synthetic_digest(cap=95)
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    with fh:
        json.dump(d, fh)
    try:
        loaded = load_digest(fh.name)
        check("rule7: sane digest loads clean", loaded["session_id"] == d["session_id"])
    finally:
        os.unlink(fh.name)

    # 10. Multi-violation: several rules broken at once → ALL appear in output.
    d = _synthetic_digest(cap=85)
    bd = {"planning": 15, "context": 15, "decomposition": 15, "delegation": 18,
          "verification": 20, "token_efficiency": 12, "documentation": 5}  # sums to 100
    s = _valid_submission_for(d, total_score=100, breakdown=bd, misses=["cuma satu"])
    s["transcript_meta"] = copy.deepcopy(s["transcript_meta"])
    s["transcript_meta"]["line_count"] += 1
    v = validate(d, s)
    check(
        "multi-violation: misses fires",
        any("misses" in m for m in v),
        v,
    )
    check(
        "multi-violation: cap struktural fires",
        any("cap struktural" in m for m in v),
        v,
    )
    check(
        "multi-violation: score_caps.cap fires",
        any("score_caps.cap" in m for m in v),
        v,
    )
    check(
        "multi-violation: transcript_meta fires",
        any("transcript_meta" in m for m in v),
        v,
    )
    check("multi-violation: 4 distinct rules all reported", len(v) >= 4, v)

    return ok


def _parse_args(argv):
    digest_path = None
    submission_path = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--digest" and i + 1 < len(argv):
            digest_path = argv[i + 1]
            i += 2
        elif a == "--submission" and i + 1 < len(argv):
            submission_path = argv[i + 1]
            i += 2
        else:
            i += 1
    return digest_path, submission_path


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        ok = _selftest()
        sys.exit(0 if ok else 1)

    digest_path, submission_path = _parse_args(argv)
    if not digest_path or not submission_path:
        sys.stderr.write(
            "usage: validate.py --digest DIGEST.json --submission SUBMISSION.json | --selftest\n"
        )
        sys.exit(2)

    try:
        digest = load_digest(digest_path)
    except DigestInvalid as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)

    try:
        submission = load_submission(submission_path)
    except ValueError as e:
        sys.stderr.write(f"VALIDATION FAIL: {e}\n")
        sys.exit(2)

    violations = validate(digest, submission)
    if violations:
        for v in violations:
            sys.stderr.write(f"VALIDATION FAIL: {v}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
