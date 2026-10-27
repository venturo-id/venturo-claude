"""Test dukungan multi-bahasa: analyzer per bahasa, deteksi stack, doc-sync per stack,
kinerja_status & hook di repo non-Go.

Jalur presisi TS/JS butuh `node` + typescript. Set VENTURO_KINERJA_TEST_TS ke folder
`node_modules/typescript` mana pun untuk menjalankannya; tanpa itu test presisi dilewati
(test fallback heuristik tetap jalan).
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

import fixture_repo as fx
import lang_fixtures as lf
from _helpers import PLUGIN_DIR

import kinerja_lib as lib
import kinerja_status as ks
import thresholds as thr

HOOK = os.path.join(PLUGIN_DIR, "hooks", "run.sh")
TS_DIR = os.environ.get("VENTURO_KINERJA_TEST_TS", "")
HAS_TS = bool(TS_DIR) and os.path.isfile(os.path.join(TS_DIR, "package.json")) and shutil.which("node")
ROLES_CAUGHT = {"long": "function_length", "deep": "nesting_depth", "many": "parameter_count", "magic": "magic_values"}


def short(name):
    return name.rsplit(".", 1)[-1]


def link_typescript(directory):
    os.makedirs(os.path.join(directory, "node_modules"), exist_ok=True)
    os.symlink(TS_DIR, os.path.join(directory, "node_modules", "typescript"))


class TmpDir(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.realpath(tempfile.mkdtemp(prefix="kinerja-lang-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestAnalyzers(TmpDir):

    def check_fixture(self, lang, rep):
        _, _, roles = lf.FIXTURES[lang]
        by_symbol = {}
        for v in rep["violations"]:
            by_symbol.setdefault(short(v["symbol"]), set()).add(v["key"])
        for role, key in ROLES_CAUGHT.items():
            self.assertIn(key, by_symbol.get(short(roles[role]), set()), "%s: %s harus %s" % (lang, role, key))
        expected = {short(roles[r]) for r in ROLES_CAUGHT}
        self.assertEqual(set(by_symbol) - expected, set(), "%s: pelanggaran palsu %s" % (lang, by_symbol))
        funcs = {short(f["name"]): f for f in rep["functions"]}
        self.assertEqual(funcs[short(roles["five"])]["params"], 5, lang)
        self.assertEqual(funcs[short(roles["deep"])]["nesting"], 5, lang)
        self.assertGreater(funcs[short(roles["long"])]["lines"], 50, lang)

    def test_every_language_fixture(self):
        paths = lf.write_all(self.dir)
        out = thr.analyze([{"path": p, "ranges": []} for p in paths.values()])
        reports = {rep["language"]: rep for rep in out["files"]}
        for lang in lf.FIXTURES:
            with self.subTest(lang):
                self.assertNotIn("error", reports[lang])
                self.check_fixture(lang, reports[lang])
        self.assertEqual(out["analyzers"]["python"], "precise")
        for lang in ("php", "swift", "kotlin", "dart", "java"):
            self.assertEqual(out["analyzers"][lang], "heuristic")
            self.assertTrue(all(v["heuristic"] for v in reports[lang]["violations"]))
        if not HAS_TS:  # tanpa node_modules/typescript: fallback heuristik
            self.assertEqual(out["analyzers"]["typescript"], "heuristic")

    def test_parameter_edge_cases(self):
        paths = lf.write_all(self.dir)
        out = thr.analyze([{"path": p, "ranges": []} for p in paths.values()])
        params = {(rep["language"], short(f["name"])): f["params"] for rep in out["files"] for f in rep["functions"]}
        self.assertEqual(params[("typescript", "destructured")], 2)  # satu objek destructuring = 1
        self.assertEqual(params[("python", "static_five")], 5)
        self.assertEqual(params[("python", "five")], 5)               # self tidak dihitung
        for lang in ("swift", "kotlin", "java"):
            self.assertEqual(params[(lang, "generic")], 2, lang)      # koma di dalam <...> bukan pemisah
        self.assertEqual(params[("dart", "named")], 3)                # {required b, c} dihitung per item

    def test_ranges_limit_to_touched_functions(self):
        path = lf.write_all(self.dir)["kotlin"]
        rep = thr.analyze([{"path": path, "ranges": [[1, 3]]}])["files"][0]
        self.assertEqual(rep["violations"], [])

    @unittest.skipUnless(HAS_TS, "VENTURO_KINERJA_TEST_TS tidak diset")
    def test_typescript_precise(self):
        link_typescript(self.dir)
        paths = []
        for lang in ("typescript", "javascript"):
            name, src, _ = lf.FIXTURES[lang]
            paths.append(os.path.join(self.dir, name))
            with open(paths[-1], "w", encoding="utf-8") as fh:
                fh.write(src)
        out = thr.analyze([{"path": p, "ranges": []} for p in paths])
        self.assertEqual(out["analyzers"], {"typescript": "precise", "javascript": "precise"})
        for rep in out["files"]:
            self.check_fixture(rep["language"], rep)
            self.assertFalse(any(v["heuristic"] for v in rep["violations"] if v["key"] != "magic_values"))
            self.assertIn("Repo.five", [f["name"] for f in rep["functions"]])

    def test_ui_components(self):
        for lang in lf.UI_COMPONENTS:
            with self.subTest(lang):
                rep = thr.analyze([{"path": lf.write_ui(self.dir, lang), "ranges": []}])["files"][0]
                self.assertTrue(rep["ui_component"], lang)
                self.assertIn("ui_component_length", [v["key"] for v in rep["violations"]])
        plain = os.path.join(self.dir, "util.ts")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write("export const x = 1;\n" * 310)
        rep = thr.analyze([{"path": plain, "ranges": []}])["files"][0]
        self.assertFalse(rep["ui_component"])
        self.assertEqual(rep["violations"], [])  # 310 baris < file_length 800

    def test_vendor_and_generated_skipped(self):
        gen = os.path.join(self.dir, "api.pb.ts")
        with open(gen, "w", encoding="utf-8") as fh:
            fh.write("// Code generated by protoc-gen-ts. DO NOT EDIT.\nexport const a = 1;\n")
        for path in ["node_modules/x/index.js", "vendor/a/B.php", "dist/app.js", ".next/s.js", "Pods/X.swift",
                     "build/x.kt", "app.min.js", "types.d.ts", "package-lock.json", gen]:
            self.assertFalse(thr.analyzable(path), path)
        self.assertTrue(thr.analyzable("src/app.tsx"))
        self.assertIsNone(thr.language_of("README.md"))


class TestStacks(TmpDir):

    def write(self, rel, content=""):
        return fx.write(self.dir, rel, content)

    def ids(self):
        return sorted((s["id"], s.get("framework"), s["path"]) for s in lib.detect_stacks(self.dir))

    def test_manifests(self):
        self.write("web/package.json", json.dumps({"dependencies": {"next": "16", "react": "19"},
                                                    "devDependencies": {"typescript": "5"}}))
        self.write("mobile/pubspec.yaml", "name: app\n")
        self.write("api/composer.json", '{"require": {"laravel/framework": "^11"}}')
        self.write("svc/requirements.txt", "fastapi==0.110\n")
        self.write("ios/Package.swift", "// swift-tools-version:5.9\n")
        self.write("android/build.gradle.kts", 'plugins { id("com.android.application"); kotlin("android") }\n')
        self.write("apps/rn/package.json", json.dumps({"dependencies": {"react-native": "0.76"}}))
        self.write("apps/be/package.json", json.dumps({"dependencies": {"express": "5"}}))
        self.write("node_modules/x/package.json", "{}")
        self.assertEqual(self.ids(), [
            ("flutter", "flutter", "mobile"), ("ios-swift", None, "ios"), ("kotlin", "android", "android"),
            ("node", "express", "apps/be"), ("php", "laravel", "api"), ("python", "fastapi", "svc"),
            ("react", "nextjs", "web"), ("react-native", "react-native", "apps/rn")])
        rules = {s["id"]: s["rules"] for s in lib.detect_stacks(self.dir)}
        self.assertEqual(rules["php"], ["php", "php/laravel"])
        self.assertEqual(rules["python"], [])

    def test_unknown_repo(self):
        self.write("README.md", "# x\n")
        self.assertEqual(lib.detect_stacks(self.dir), [])

    def test_doc_sync_per_stack(self):
        cases = [
            ({"react"}, "src/app/api/revalidate/route.ts"), ({"react"}, "src/module/core/features/users/api/index.ts"),
            ({"react"}, "src/lib/api/articles.ts"), ({"node"}, "src/users/users.controller.ts"),
            ({"php"}, "routes/api.php"), ({"php"}, "app/Http/Controllers/UserController.php"),
            ({"python"}, "app/routers/users.py"), ({"python"}, "alembic/versions/0001_init.py"),
        ]
        for stacks, path in cases:
            with self.subTest(path):
                doc = lib.doc_sync_check([path], stacks)
                self.assertTrue(doc["applicable"] and not doc["updated"], doc)
                self.assertTrue(lib.doc_sync_check([path, "docs/api/users.md"], stacks)["updated"])
        self.assertFalse(lib.doc_sync_check(["src/components/button.tsx"], {"react"})["applicable"])
        self.assertFalse(lib.doc_sync_check(["src/users/users.controller.spec.ts"], {"node"})["applicable"])


def make_react_repo(with_ts=False):
    repo = os.path.realpath(tempfile.mkdtemp(prefix="kinerja-react-"))
    fx.git(repo, "init", "-q", "-b", "production")
    fx.write(repo, "package.json", json.dumps({"dependencies": {"react": "19"}, "devDependencies": {"typescript": "5"}}))
    fx.write(repo, "tsconfig.json", "{}")
    fx.write(repo, "docs/patterns/api-layer.md", "# API\n")
    fx.write(repo, "src/module/users/api/index.ts", "export const list = () => fetch('/users');\n")
    fx.write(repo, ".gitignore", "node_modules/\n")
    fx.git(repo, "add", "-A")
    fx.git(repo, "commit", "-q", "-m", "chore: init [FE-1]")
    fx.git(repo, "checkout", "-q", "-b", "feat")
    name, src, _ = lf.FIXTURES["typescript"]
    fx.write(repo, "src/module/users/views/" + name, src)
    fx.write(repo, "src/module/users/api/index.ts", "export const list = (page: number) => fetch(`/users?p=${page}`);\n")
    fx.git(repo, "add", "-A")
    fx.git(repo, "commit", "-q", "-m", "feat(users): daftar user [FE-2]")
    if with_ts:
        link_typescript(repo)
    return repo


class TestStatusNonGo(unittest.TestCase):

    def run_status(self, with_ts):
        repo = make_react_repo(with_ts)
        try:
            started = time.time()
            st = ks.build_status(repo, "production")
            return st, time.time() - started
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def test_react_repo_heuristic(self):
        st, elapsed = self.run_status(False)
        self.assertEqual([(s["id"], s["language"]) for s in st["stacks"]], [("react", "typescript")])
        self.assertEqual(st["analyzers"], {"typescript": "heuristic"})
        self.assertEqual(st["changed"]["by_language"], {"typescript": 2})
        keys = {(v["key"] if "key" in v else v["category"], v.get("language")) for v in st["violations"]}
        self.assertIn(("function_length", "typescript"), keys)
        self.assertIn(("doc-sync", None), keys)
        self.assertTrue(all(v["heuristic"] for v in st["violations"]))
        self.assertFalse({g["id"]: g for g in st["gates"]}["doc_sync"]["ok"])
        self.assertLess(elapsed, 3.0)

    @unittest.skipUnless(HAS_TS, "VENTURO_KINERJA_TEST_TS tidak diset")
    def test_react_repo_precise(self):
        st, elapsed = self.run_status(True)
        self.assertEqual(st["analyzers"], {"typescript": "precise"})
        structural = [v for v in st["violations"] if v["dimension"] == "structural" and v["key"] != "magic_values"]
        self.assertTrue(structural and not any(v["heuristic"] for v in structural))
        self.assertLess(elapsed, 3.0)

    def test_repo_without_stack(self):
        repo = os.path.realpath(tempfile.mkdtemp(prefix="kinerja-none-"))
        try:
            fx.git(repo, "init", "-q", "-b", "production")
            fx.write(repo, "notes.txt", "a\n")
            fx.git(repo, "add", "-A")
            fx.git(repo, "commit", "-q", "-m", "docs: catatan [NT-1]")
            st = ks.build_status(repo, "production")
            self.assertEqual((st["stacks"], st["analyzers"], st["violations"]), ([], {}, []))
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class TestStacksCli(TmpDir):

    def test_stacks_flag(self):
        import io
        from contextlib import redirect_stdout
        fx.write(self.dir, "pubspec.yaml", "name: app\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(ks.main(["--stacks", "--repo", self.dir]), 0)
        self.assertEqual([s["id"] for s in json.loads(buf.getvalue())], ["flutter"])


class TestHooksNonGo(TmpDir):

    def setUp(self):
        super().setUp()
        fx.write(self.dir, ".claude/venturo-kinerja.json", fx.ENFORCE_MARKER)  # hook hanya memaksa di enforce

    def hook(self, name, event):
        proc = subprocess.run(["/bin/bash", HOOK, name], input=json.dumps(event), capture_output=True, text=True,
                              timeout=60)
        return proc.returncode, proc.stderr

    def edit(self, rel, content, old="", new=None):
        path = fx.write(self.dir, rel, content)
        return {"cwd": self.dir, "tool_name": "Edit",
                "tool_input": {"file_path": path, "old_string": old, "new_string": new if new is not None else content}}

    def test_python_repo_blocks_new_violation(self):
        fx.write(self.dir, "requirements.txt", "fastapi\n")
        code, err = self.hook("post_edit", self.edit("app/svc.py", lf.PY))
        self.assertEqual(code, 2, err)
        self.assertIn("long_fn", err)
        self.assertNotIn("(heuristik)", err)

    def test_php_repo_blocks_heuristic(self):
        fx.write(self.dir, "composer.json", '{"require": {"slim/slim": "^4"}}')
        code, err = self.hook("post_edit", self.edit("src/Repo.php", lf.PHP))
        self.assertEqual(code, 2, err)
        self.assertIn("(heuristik)", err)

    def test_ts_without_typescript_is_skipped(self):
        fx.write(self.dir, "package.json", '{"dependencies": {"react": "19"}}')
        code, err = self.hook("post_edit", self.edit("src/a.tsx", lf.TS))
        self.assertEqual(code, 0, err)

    @unittest.skipUnless(HAS_TS, "VENTURO_KINERJA_TEST_TS tidak diset")
    def test_ts_with_typescript_blocks(self):
        fx.write(self.dir, "package.json", '{"dependencies": {"react": "19"}}')
        link_typescript(self.dir)
        code, err = self.hook("post_edit", self.edit("src/a.tsx", lf.TS))
        self.assertEqual(code, 2, err)
        self.assertIn("longFn", err)

    def test_unknown_stack_is_silent(self):
        code, _ = self.hook("post_edit", self.edit("x/a.py", lf.PY))
        self.assertEqual(code, 0)

    def test_guard_commit_in_react_repo(self):
        fx.write(self.dir, "package.json", '{"dependencies": {"react": "19"}}')
        event = {"cwd": self.dir, "tool_name": "Bash", "tool_input": {"command": "git commit -m 'update'"}}
        self.assertEqual(self.hook("guard_commit", event)[0], 2)


if __name__ == "__main__":
    unittest.main()
