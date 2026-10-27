"""Test mode kepatuhan (enforce | advisory | off): resolusi, efek di status, dan hook."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import fixture_repo as fx
from _helpers import PLUGIN_DIR

import kinerja_lib as lib
import kinerja_status as ks

HOOK = os.path.join(PLUGIN_DIR, "hooks", "run.sh")
HANDLER = "internal/modules/core/user/handler/user_handler.go"

VENTURO_REMOTES = [
    "https://github.com/venturo-id/venturo-claude.git",
    "https://salim:ghp_SECRET123@github.com/venturo-id/venturo-claude.git",  # HTTPS + PAT
    "https://x-access-token:tok@github.com/venturo-id/a",
    "git@github.com:venturo-id/venturo-skeleton-go.git",
    "ssh://git@github.com/venturo-id/venturo-skeleton-go.git",
    "git+ssh://git@github.com/venturo-id/a.git",
    "https://github.com/Venturo-ID/A.git",  # nama org GitHub tidak case-sensitive
]
OTHER_REMOTES = [
    "https://github.com/salim/side-project.git",
    "https://github.com/venturo-idx/a.git",
    "https://github.com/salim/venturo-id.git",
    "git@github.com:someone/venturo-id-fork.git",
    "https://gitlab.com/venturo-id/a.git",
    "git@gitlab.com:venturo-id/a.git",
    "https://github.com.evil.example/venturo-id/a.git",
]


def init_repo():
    repo = os.path.realpath(tempfile.mkdtemp(prefix="kinerja-mode-"))
    fx.git(repo, "init", "-q", "-b", "main")
    return repo


class ModeCase(unittest.TestCase):
    def setUp(self):
        self.repo = init_repo()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop(lib.MODE_ENV, None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.repo, ignore_errors=True)

    def mode(self):
        return lib.resolve_mode(self.repo)

    def marker(self, content):
        fx.write(self.repo, ".claude/venturo-kinerja.json", content)


class TestRemoteDetection(unittest.TestCase):

    def test_urls(self):
        for url in VENTURO_REMOTES:
            self.assertTrue(lib.is_venturo_remote(url), url)
        for url in OTHER_REMOTES:
            self.assertFalse(lib.is_venturo_remote(url), url)

    def test_credentials_masked(self):
        self.assertEqual(lib.mask_url(VENTURO_REMOTES[1]), "https://***@github.com/venturo-id/venturo-claude.git")
        self.assertEqual(lib.mask_url(VENTURO_REMOTES[0]), VENTURO_REMOTES[0])


class TestResolveMode(ModeCase):

    def test_default_advisory(self):
        m = self.mode()
        self.assertEqual((m["value"], m["source"], m["warnings"]), ("advisory", "default", []))

    def test_venturo_remote_enforce(self):
        for i, url in enumerate(VENTURO_REMOTES):
            fx.git(self.repo, "remote", "add", "r%d" % i, url)
            m = self.mode()
            self.assertEqual((m["value"], m["source"]), ("enforce", "remote"), url)
            self.assertNotIn("SECRET", m["detail"])
            fx.git(self.repo, "remote", "remove", "r%d" % i)

    def test_other_remotes_stay_advisory(self):
        for i, url in enumerate(OTHER_REMOTES):
            fx.git(self.repo, "remote", "add", "r%d" % i, url)
        self.assertEqual(self.mode()["source"], "default")

    def test_marker(self):
        fx.git(self.repo, "remote", "add", "origin", VENTURO_REMOTES[0])
        for value in ("advisory", "off", "enforce"):
            self.marker(json.dumps({"mode": value}))
            m = self.mode()
            self.assertEqual((m["value"], m["source"], m["detail"]), (value, "marker", ".claude/venturo-kinerja.json"))

    def test_invalid_marker_falls_through(self):
        fx.git(self.repo, "remote", "add", "origin", VENTURO_REMOTES[3])
        for content in ("{bukan json", json.dumps({"mode": "strict"}), json.dumps({"other": 1}), "[]"):
            self.marker(content)
            m = self.mode()
            self.assertEqual((m["value"], m["source"]), ("enforce", "remote"), content)
            self.assertEqual(len(m["warnings"]), 1, content)

    def test_git_config_beats_marker_and_remote(self):
        fx.git(self.repo, "remote", "add", "origin", VENTURO_REMOTES[0])
        self.marker('{"mode": "enforce"}')
        fx.git(self.repo, "config", "kinerja.mode", "off")
        m = self.mode()
        self.assertEqual((m["value"], m["source"], m["detail"]), ("off", "git-config", "git config kinerja.mode=off"))

    def test_global_git_config_and_repo_precedence(self):
        global_cfg = os.path.join(self.repo, "..", os.path.basename(self.repo) + ".gitconfig")
        with open(global_cfg, "w", encoding="utf-8") as fh:
            fh.write("[kinerja]\n\tmode = off\n")
        try:
            os.environ["GIT_CONFIG_GLOBAL"] = global_cfg
            self.assertEqual((self.mode()["value"], self.mode()["source"]), ("off", "git-config"))
            subprocess.run(["git", "-C", self.repo, "config", "--local", "kinerja.mode", "enforce"], check=True)
            self.assertEqual(self.mode()["value"], "enforce")  # config repo menang atas global
        finally:
            os.unlink(global_cfg)

    def test_invalid_git_config_falls_through(self):
        self.marker('{"mode": "off"}')
        fx.git(self.repo, "config", "kinerja.mode", "maybe")
        m = self.mode()
        self.assertEqual((m["value"], m["source"]), ("off", "marker"))
        self.assertIn("maybe", m["warnings"][0])

    def test_env_beats_everything(self):
        fx.git(self.repo, "remote", "add", "origin", VENTURO_REMOTES[0])
        self.marker('{"mode": "off"}')
        fx.git(self.repo, "config", "kinerja.mode", "off")
        os.environ[lib.MODE_ENV] = " ENFORCE "
        m = self.mode()
        self.assertEqual((m["value"], m["source"]), ("enforce", "env"))

    def test_invalid_env_falls_through(self):
        fx.git(self.repo, "config", "kinerja.mode", "advisory")
        os.environ[lib.MODE_ENV] = "yes"
        m = self.mode()
        self.assertEqual((m["value"], m["source"]), ("advisory", "git-config"))
        self.assertIn("VENTURO_KINERJA_MODE", m["warnings"][0])

    def test_priority_ladder(self):
        """Lepas sumber satu per satu dari atas: env → git-config → marker → remote → default."""
        fx.git(self.repo, "remote", "add", "origin", VENTURO_REMOTES[0])
        self.marker('{"mode": "off"}')
        fx.git(self.repo, "config", "kinerja.mode", "advisory")
        os.environ[lib.MODE_ENV] = "enforce"
        seen = [(self.mode()["source"], self.mode()["value"])]
        del os.environ[lib.MODE_ENV]
        seen.append((self.mode()["source"], self.mode()["value"]))
        fx.git(self.repo, "config", "--unset", "kinerja.mode")
        seen.append((self.mode()["source"], self.mode()["value"]))
        os.unlink(os.path.join(self.repo, ".claude", "venturo-kinerja.json"))
        seen.append((self.mode()["source"], self.mode()["value"]))
        fx.git(self.repo, "remote", "remove", "origin")
        seen.append((self.mode()["source"], self.mode()["value"]))
        self.assertEqual(seen, [("env", "enforce"), ("git-config", "advisory"), ("marker", "off"),
                                ("remote", "enforce"), ("default", "advisory")])

    def test_cli_mode_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(ks.main(["--mode", "--repo", self.repo]), 0)
        self.assertEqual(json.loads(buf.getvalue())["value"], "advisory")


class TestStatusByMode(unittest.TestCase):
    """Fixture: penanda enforce di-commit; commit `update handler` melanggar gate."""

    def setUp(self):
        self.repo = fx.make_repo()

    def tearDown(self):
        fx.remove(self.repo)

    def status(self, mode=None):
        env = {lib.MODE_ENV: mode} if mode else {}
        with mock.patch.dict(os.environ, env):
            return ks.build_status(self.repo, "production")

    def test_enforce_blocks(self):
        st = self.status()
        self.assertEqual(st["mode"], {"value": "enforce", "source": "marker", "detail": ".claude/venturo-kinerja.json"})
        self.assertEqual((st["predicted"]["status"], st["predicted"]["blocked_by"]), ("blocked", ["commit_format"]))
        gates = {g["id"]: g for g in st["gates"]}
        self.assertEqual((gates["commit_format"]["effect"], gates["changelog"]["effect"]), ("unscored", "ci"))

    def test_advisory_does_not_block(self):
        st = self.status("advisory")
        self.assertEqual((st["mode"]["value"], st["mode"]["source"]), ("advisory", "env"))
        self.assertEqual((st["predicted"]["status"], st["predicted"]["blocked_by"]), ("scored", []))
        gates = {g["id"]: g for g in st["gates"]}
        self.assertFalse(gates["commit_format"]["ok"])  # tetap dilaporkan, hanya tidak diwajibkan
        self.assertEqual((gates["commit_format"]["effect"], gates["changelog"]["effect"]), ("info", "info"))
        self.assertEqual(st["predicted"]["final"], 77)  # prediksi & pelanggaran tetap dihitung
        self.assertTrue(st["violations"])
        self.assertIn("Mode saran (env): estimasi, tidak diwajibkan", ks.format_text(st))

    def test_off_still_runs_manually(self):
        st = self.status("off")
        self.assertEqual(st["mode"]["value"], "off")
        self.assertEqual(st["predicted"]["status"], "scored")
        self.assertIn("Mode off", ks.format_text(st))


class TestHooksByMode(unittest.TestCase):
    """advisory & off: tidak ada hook yang memblokir atau memaksa Claude."""

    def setUp(self):
        self.repo = fx.make_repo()

    def tearDown(self):
        fx.remove(self.repo)

    def hook(self, name, event, mode):
        env = dict(os.environ, **({lib.MODE_ENV: mode} if mode else {}))
        proc = subprocess.run(["/bin/bash", HOOK, name], input=json.dumps(event), capture_output=True,
                              text=True, env=env, timeout=120)
        return proc.returncode, proc.stdout

    def events(self):
        path = os.path.join(self.repo, HANDLER)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        addition = fx.long_func("Import", "a int")
        fx.write(self.repo, HANDLER, content + addition)
        return {
            "guard_commit": {"cwd": self.repo, "tool_name": "Bash", "tool_input": {"command": "git commit -m 'oops'"}},
            "post_edit": {"cwd": self.repo, "tool_name": "Edit",
                          "tool_input": {"file_path": path, "old_string": "", "new_string": addition}},
            "post_edit_claude_md": {"cwd": self.repo, "tool_name": "Edit",
                                    "tool_input": {"file_path": os.path.join(self.repo, "CLAUDE.md"),
                                                   "old_string": "a", "new_string": "b"}},
            "stop_doc_sync": {"cwd": self.repo, "stop_hook_active": False},
        }

    def test_enforce_baseline(self):
        ev = self.events()
        self.assertEqual(self.hook("guard_commit", ev["guard_commit"], None)[0], 2)
        self.assertEqual(self.hook("post_edit", ev["post_edit"], None)[0], 2)

    def test_advisory_and_off_never_block(self):
        ev = self.events()
        for mode in ("advisory", "off"):
            for name, event in ev.items():
                hook = "post_edit" if name.startswith("post_edit") else name
                with self.subTest(mode=mode, hook=name):
                    code, out = self.hook(hook, event, mode)
                    self.assertEqual((code, out), (0, ""))

    def test_git_config_advisory_silences_hooks(self):
        fx.git(self.repo, "config", "kinerja.mode", "advisory")
        ev = self.events()
        self.assertEqual(self.hook("guard_commit", ev["guard_commit"], None), (0, ""))
        self.assertEqual(self.hook("post_edit", ev["post_edit"], None), (0, ""))

    def test_session_start_by_mode(self):
        sys.path.insert(0, os.path.join(PLUGIN_DIR, "hooks"))
        import session_start
        stale = dict(lib.rules_info(), stale=True, age_days=20.0)
        for mode, should_warn in (("enforce", True), ("advisory", False), ("off", False)):
            buf = io.StringIO()
            with mock.patch.object(session_start.lib, "rules_info", return_value=stale), \
                    mock.patch.dict(os.environ, {lib.MODE_ENV: mode}), redirect_stdout(buf):
                try:
                    session_start.main({"cwd": self.repo})
                except SystemExit:
                    pass
            self.assertEqual(bool(buf.getvalue()), should_warn, mode)


if __name__ == "__main__":
    unittest.main()
