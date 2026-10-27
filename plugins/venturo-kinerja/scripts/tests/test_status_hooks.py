"""Test kinerja_status.py, kinerja_lib, render_rule, dan hook (input JSON contoh).

Memakai repo git sementara (fixture_repo.py). Butuh `git`; bagian Go dilewati
bila `go` tidak ada (sama dengan perilaku plugin).
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import fixture_repo as fx
from _helpers import PLUGIN_DIR

import kinerja_lib as lib
import kinerja_status as ks
import render_rule

HOOK = os.path.join(PLUGIN_DIR, "hooks", "run.sh")
HAS_GO = shutil.which("go") is not None
HANDLER = "internal/modules/core/user/handler/user_handler.go"
_CACHE = tempfile.mkdtemp(prefix="kinerja-cache-")


def run_hook(name, event, env=None):
    proc = subprocess.run(["/bin/bash", HOOK, name], input=json.dumps(event), capture_output=True, text=True,
                          env=dict(os.environ, CLAUDE_PLUGIN_DATA=_CACHE, **(env or {})), timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def tearDownModule():
    shutil.rmtree(_CACHE, ignore_errors=True)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        os.environ["CLAUDE_PLUGIN_DATA"] = _CACHE
        self.repo = fx.make_repo()

    def tearDown(self):
        fx.remove(self.repo)

    def status(self):
        return ks.build_status(self.repo, "production")


@unittest.skipUnless(HAS_GO, "go tidak terpasang")
class TestKinerjaStatus(FixtureCase):

    def test_contract_shape(self):
        st = self.status()
        for key in ("schema_version", "base", "head", "diff_hash", "predicted", "violations", "gates", "rules"):
            self.assertIn(key, st)
        self.assertEqual(st["schema_version"], 1)
        self.assertEqual(set(st["predicted"]["dimensions"]), {"bug", "structural", "readability", "doc_sync"})
        self.assertEqual(set(st["rules"]), {"synced_at", "age_days", "stale", "stale_after_days",
                                            "kinerja_be_commit", "versions"})
        json.dumps(st)  # harus bisa diserialisasi apa adanya

    def test_static_prediction(self):
        # structural 2 temuan → 80; doc_sync applicable tanpa dokumen → 0; bug skipped
        # final = (80×30 + 100×30 + 0×10) / 70 = 77.1 → 77
        p = self.status()["predicted"]
        dims = {k: v["score"] for k, v in p["dimensions"].items()}
        self.assertEqual(dims, {"bug": None, "structural": 80, "readability": 100, "doc_sync": 0})
        # commit "update handler" melanggar gate → PR tidak dinilai; angka = skor bila gate lolos
        self.assertEqual((p["final"], p["status"], p["source"]), (77, "blocked", "static"))
        self.assertEqual(p["blocked_by"], ["commit_format"])

    def test_violations_and_points(self):
        all_v = self.status()["violations"]
        vs = {(v["category"], v["file"]): v for v in all_v}
        self.assertEqual(vs[("oversized-function", HANDLER)]["symbol"], "Export")
        self.assertEqual(vs[("oversized-function", HANDLER)]["points_final"], 4)   # 77 → 81
        self.assertEqual(vs[("too-many-parameters", HANDLER)]["points_final"], 4)
        doc = [v for v in vs.values() if v["category"] == "doc-sync"][0]
        self.assertEqual(doc["points_final"], 14)                                  # 77 → 91
        agent = [v for v in all_v if v["category"] == "agent-docs"]
        self.assertEqual(len(agent), 2)                                            # ukuran + delegasi
        self.assertEqual(agent[0]["points_final"], 5)                              # bug 70→85: 75 → 79.5 → 80

    def test_violations_sorted_by_points(self):
        pts = [v["points_final"] for v in self.status()["violations"]]
        self.assertEqual(pts, sorted(pts, reverse=True))

    def test_gates(self):
        gates = {g["id"]: g for g in self.status()["gates"]}
        self.assertFalse(gates["commit_format"]["ok"])
        self.assertIn("update handler", gates["commit_format"]["items"][0])
        self.assertTrue(gates["trivial_pr"]["ok"])
        self.assertFalse(gates["agent_docs"]["ok"])
        self.assertFalse(gates["doc_sync"]["ok"])
        self.assertIn("docs/erd/core.mmd", " ".join(gates["doc_sync"]["items"]))
        self.assertFalse(gates["changelog"]["ok"])
        self.assertTrue(gates["rules_fresh"]["ok"] or gates["rules_fresh"]["effect"] == "info")

    def test_docs_fix_flips_doc_sync(self):
        fx.write(self.repo, "docs/api-contract/core/user.md", "# User\n\n**Last Updated:** 2026-10-26\n")
        fx.write(self.repo, "docs/erd/core.mmd", "erDiagram\n")
        st = self.status()
        self.assertEqual(st["predicted"]["dimensions"]["doc_sync"]["score"], 100)
        self.assertTrue({g["id"]: g for g in st["gates"]}["doc_sync"]["ok"])

    def test_precheck_freshness(self):
        findings = os.path.join(self.repo, "..", os.path.basename(self.repo) + "-pre.json")
        with open(findings, "w", encoding="utf-8") as fh:
            json.dump({"findings": [{"severity": "critical"}, {"severity": "critical"}, {"severity": "medium"}],
                       "quality": {"findings": [{"category": "naming-convention",
                                                 "evidence": HANDLER + ":3", "note": "x"}]}}, fh)
        try:
            ks.record_precheck(self.repo, "production", findings)
        finally:
            os.unlink(findings)
        st = self.status()
        self.assertTrue(st["precheck"]["fresh"])
        self.assertEqual(st["predicted"]["source"], "precheck")
        self.assertEqual(st["predicted"]["dimensions"]["bug"]["score"], 65)
        self.assertEqual(st["predicted"]["dimensions"]["readability"]["score"], 90)
        # file state precheck tidak ikut diff (di-.gitignore sendiri)
        self.assertNotIn(".claude/venturo-kinerja/last-precheck.json",
                         [f["path"] for f in ks.changed_files(self.repo, st["base"]["merge_base"])])
        fx.write(self.repo, HANDLER, fx.HANDLER)  # kode berubah → precheck basi
        st2 = self.status()
        self.assertFalse(st2["precheck"]["fresh"])
        self.assertTrue(st2["predicted"]["dimensions"]["bug"]["skipped"])

    def test_valid_commits_are_scored(self):
        fx.git(self.repo, "commit", "-q", "--amend", "-m", "feat(user): export [FX-2]")
        p = self.status()["predicted"]
        self.assertEqual((p["status"], p["blocked_by"]), ("scored", []))

    def test_diff_hash_stable(self):
        self.assertEqual(self.status()["diff_hash"], self.status()["diff_hash"])

    def test_cli_json_and_text(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ks.main(["--json", "--base", "production", "--repo", self.repo])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["predicted"]["final"], 77)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ks.main(["--base", "production", "--repo", self.repo])
        self.assertIn("Prediksi skor final: 77", buf.getvalue())

    def test_unknown_base_is_error(self):
        with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(ks.main(["--base", "tidak-ada", "--repo", self.repo]), 2)

    def test_auto_base(self):
        self.assertEqual(ks.build_status(self.repo)["base"]["ref"], "production")

    def test_configured_base(self):
        fx.git(self.repo, "branch", "release", "production")
        fx.git(self.repo, "config", "kinerja.base", "release")
        self.assertEqual(ks.build_status(self.repo)["base"]["ref"], "release")
        with unittest.mock.patch.dict(os.environ, {"VENTURO_KINERJA_BASE": "production"}):
            self.assertEqual(ks.build_status(self.repo)["base"]["ref"], "production")


class TestLib(unittest.TestCase):

    def test_commit_rules(self):
        # pola = conventional_commit.go + space_issue_gate.go (prefix 2–6 karakter)
        ok = ["feat(user): tambah filter [ABC-12]", "Fix!: perbaiki [kj-399]", "chore: x\n\nRefs [AB-1]",
              "Merge branch 'x'", 'Revert "feat: y"']
        bad = ["update handler", "feat: tanpa kode", "feature: x [AB-1]", "feat: x [A-1]", "feat: x [ABCDEFG-1]"]
        for msg in ok:
            self.assertEqual(lib.commit_message_problems(msg), [], msg)
        for msg in bad:
            self.assertNotEqual(lib.commit_message_problems(msg), [], msg)

    def test_render_placeholders(self):
        text = lib.render_placeholders("{{SEVERITY_PENALTIES}} | {{SEVERITY_SCOPE}} | {{VERDICT_MEDIUM_RULE}}")
        self.assertEqual(text, "critical 15, high 10, medium 5, low 2, info 0 | Critical/High/Medium | "
                               "- ada Medium: `Verdict: Needs work`")
        self.assertNotIn("{{", lib.read_rule("quality-score/bug"))
        self.assertIn("{{SEVERITY_PENALTIES}}", lib.read_rule("quality-score/bug", render=False))

    def test_doc_sync_mapping(self):
        doc = lib.doc_sync_check(["internal/modules/core/user/dto/user.go", "internal/router/router.go",
                                  "internal/modules/core/user/service/user_test.go"])
        self.assertEqual(doc["missing"], ["internal/modules/core/user/dto/user.go -> docs/api-contract/core/",
                                          "internal/router/router.go -> docs/api-contract/"])
        self.assertFalse(lib.doc_sync_check(["internal/modules/core/user/service/x.go"])["applicable"])

    def test_render_rule_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            render_rule.main(["--thresholds"])
        self.assertEqual(json.loads(buf.getvalue())["function_length"], 50)


class TestSkillMatchesRules(unittest.TestCase):
    """Tabel ambang di SKILL venturo-kinerja-rules harus sama dengan rules/quality-score/structural.md."""

    def test_threshold_table(self):
        with open(os.path.join(PLUGIN_DIR, "skills", "venturo-kinerja-rules", "SKILL.md"), encoding="utf-8") as fh:
            skill = fh.read()
        for key, value in lib.structural_thresholds().items():
            self.assertIn("| %s | %d |" % (key, value), skill)

    def test_plugin_layout(self):
        with open(os.path.join(PLUGIN_DIR, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        for groups in hooks.values():
            for g in groups:
                for h in g["hooks"]:
                    name = h["command"].rsplit(" ", 1)[1]
                    self.assertTrue(os.path.isfile(os.path.join(PLUGIN_DIR, "hooks", name + ".py")), name)
        for name in os.listdir(os.path.join(PLUGIN_DIR, "skills")):
            self.assertTrue(name.startswith("venturo-"), name)


class TestGuardCommitHook(FixtureCase):

    def check(self, command, want_block):
        code, _, err = run_hook("guard_commit", {"cwd": self.repo, "tool_name": "Bash",
                                                 "tool_input": {"command": command}})
        self.assertEqual(code, 2 if want_block else 0, (command, err))
        return err

    def test_messages(self):
        self.assertIn("kode issue", self.check("git commit -m 'feat: tambah export'", True))
        self.check("git add -A && git commit -m 'update'", True)
        self.check("git commit -am 'feat(user): export [FX-2]'", False)
        self.check('git commit -m "fix: x" -m "Refs [FX-3]"', False)
        self.check("git commit --message='docs: y [FX-4]'", False)
        self.check("git -C %s commit -m 'oops'" % self.repo, True)

    def test_cd_into_repo_from_other_folder(self):
        # Sesi dibuka di folder induk (bukan repo git): repo tujuan diambil dari `cd`.
        parent = tempfile.mkdtemp()
        try:
            def run(command):
                code, _, err = run_hook("guard_commit", {"cwd": parent, "tool_name": "Bash",
                                                         "tool_input": {"command": command}})
                return code, err
            self.assertEqual(run("cd %s && git commit -m 'oops'" % self.repo)[0], 2)
            self.assertEqual(run("cd '%s'; git add -A && git commit -m 'oops'" % self.repo)[0], 2)
            self.assertEqual(run("cd %s && git commit -m 'feat(user): x [FX-9]'" % self.repo)[0], 0)
            self.assertEqual(run("git commit -m 'oops'")[0], 0)  # folder induk bukan repo: dilewati
        finally:
            shutil.rmtree(parent, ignore_errors=True)

    def test_heredoc(self):
        good = "git commit -m \"$(cat <<'EOF'\nfeat(user): export [FX-5]\n\nBody.\nEOF\n)\""
        bad = "git commit -m \"$(cat <<'EOF'\nupdate handler\n\nBody.\nEOF\n)\""
        self.check(good, False)
        self.check(bad, True)

    def test_unsure_is_skipped(self):
        for cmd in ["git commit", "git commit -F msg.txt", "git commit --amend --no-edit",
                    "git commit -m \"$MSG\"", "git commit -m \"$(generate)\"", "git commit -C HEAD",
                    "git status", "echo 'git commit -m x'x"]:
            self.check(cmd, False)

    def test_non_go_repo_silent(self):
        os.unlink(os.path.join(self.repo, "go.mod"))
        self.check("git commit -m 'update'", False)


@unittest.skipUnless(HAS_GO, "go tidak terpasang")
class TestPostEditHook(FixtureCase):

    def edit_event(self, rel, old, new):
        return {"cwd": self.repo, "tool_name": "Edit",
                "tool_input": {"file_path": os.path.join(self.repo, rel), "old_string": old, "new_string": new}}

    def test_new_long_function_blocks(self):
        path = os.path.join(self.repo, HANDLER)
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        addition = fx.long_func("Import", "a int")
        fx.write(self.repo, HANDLER, before + addition)
        code, _, err = run_hook("post_edit", self.edit_event(HANDLER, "", addition))
        # Edit dengan old_string kosong tidak bisa direkonstruksi → dibanding HEAD
        self.assertEqual(code, 2, err)
        self.assertIn("Import", err)
        self.assertIn("oversized-function", err)
        self.assertNotIn("Export", err)  # pelanggaran lama (sudah ada di HEAD) tidak diulang

    def test_edit_elsewhere_is_quiet(self):
        path = os.path.join(self.repo, HANDLER)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        fx.write(self.repo, HANDLER, content.replace('return "pong"', 'return "PONG"'))
        code, _, err = run_hook("post_edit", self.edit_event(HANDLER, 'return "pong"', 'return "PONG"'))
        self.assertEqual(code, 0, err)

    def test_growing_existing_violation_blocks(self):
        path = os.path.join(self.repo, HANDLER)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        new = content.replace("\treturn total\n", "\ttotal += a\n\treturn total\n", 1)
        fx.write(self.repo, HANDLER, new)
        code, _, err = run_hook("post_edit", self.edit_event(HANDLER, "\treturn total\n",
                                                             "\ttotal += a\n\treturn total\n"))
        self.assertEqual(code, 2, err)
        self.assertIn("Export", err)

    def test_claude_md_too_long(self):
        code, _, err = run_hook("post_edit", self.edit_event("CLAUDE.md", "a", "b"))
        self.assertEqual(code, 2)
        self.assertIn("210 baris > 200", err)
        self.assertIn("delegasi", err)

    def test_claude_md_ok(self):
        fx.write(self.repo, "CLAUDE.md", fx.CLEAN_CLAUDE_MD)
        self.assertEqual(run_hook("post_edit", self.edit_event("CLAUDE.md", "a", "b"))[0], 0)

    def test_non_go_and_missing_tools(self):
        self.assertEqual(run_hook("post_edit", self.edit_event("README.md", "a", "b"))[0], 0)
        empty = tempfile.mkdtemp()
        try:  # tanpa python3/go di PATH: lewati, jangan blok
            proc = subprocess.run(["/bin/bash", HOOK, "post_edit"], input="{}", capture_output=True,
                                  text=True, env={"PATH": empty})
            self.assertEqual(proc.returncode, 0)
            os.symlink(sys.executable, os.path.join(empty, "python3"))  # python ada, go & git tidak
            code, _, _ = run_hook("post_edit", self.edit_event(HANDLER, "x", "y"), env={"PATH": empty})
            self.assertEqual(code, 0)
        finally:
            shutil.rmtree(empty)


class TestStopAndSessionHooks(FixtureCase):

    def test_stop_reminds_once(self):
        code, out, _ = run_hook("stop_doc_sync", {"cwd": self.repo, "stop_hook_active": False})
        self.assertEqual(code, 0)
        reply = json.loads(out)
        self.assertEqual(reply["decision"], "block")
        self.assertIn("docs/erd/core.mmd", reply["reason"])
        self.assertIn("CHANGELOG.md", reply["reason"])
        self.assertEqual(run_hook("stop_doc_sync", {"cwd": self.repo})[1], "")  # diff sama: diam

    def test_stop_hook_active_and_docs_present(self):
        self.assertEqual(run_hook("stop_doc_sync", {"cwd": self.repo, "stop_hook_active": True})[1], "")
        fx.write(self.repo, "docs/api-contract/core/user.md", "# User v2\n")
        fx.write(self.repo, "docs/erd/core.mmd", "erDiagram\n")
        fx.write(self.repo, "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n- export\n")
        self.assertEqual(run_hook("stop_doc_sync", {"cwd": self.repo})[1], "")

    def test_session_start(self):
        self.assertEqual(run_hook("session_start", {"cwd": self.repo})[1], "")  # rules segar: diam
        sys.path.insert(0, os.path.join(PLUGIN_DIR, "hooks"))
        import session_start
        stale = dict(lib.rules_info(), stale=True, age_days=20.0)
        buf = io.StringIO()
        with unittest.mock.patch.object(session_start.lib, "rules_info", return_value=stale), \
                redirect_stdout(buf), self.assertRaises(SystemExit):
            session_start.main({"cwd": self.repo})
        reply = json.loads(buf.getvalue())
        self.assertIn("20 hari", reply["systemMessage"])
        self.assertEqual(reply["hookSpecificOutput"]["hookEventName"], "SessionStart")


import unittest.mock  # noqa: E402  (dipakai di atas lewat atribut modul)

if __name__ == "__main__":
    unittest.main()
