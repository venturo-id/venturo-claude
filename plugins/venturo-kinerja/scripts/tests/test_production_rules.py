"""Test terhadap snapshot rules production + tabel simulasi plan.

Vector skenario diturunkan dari "plan-review-ready-base-repo-plugin.md" bagian 2.3
(tabel "Simulasi (untuk materi engineer)", 26 Okt 2026): final 99, 78, 88, 90.
Semuanya dihitung dengan config dari rules/quality-score*.md (per_finding 10).
"""
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _helpers import RULES_DIR, SCRIPTS_DIR, simulate_score as s

FILES = [{"path": "internal/modules/user/service.go", "additions": 120, "deletions": 8}]
GO = "internal/modules/user/service.go"


def scenario(severities, quality_findings, applicable=False, updated=None):
    return {
        "findings": [{"severity": sev} for sev in severities],
        "quality": {"findings": quality_findings, "doc_sync_applicable": applicable,
                    "doc_sync_updated": updated},
        "changed_files": FILES,
    }


def finding(category, line):
    return {"category": category, "evidence": "%s:%d" % (GO, line), "note": ""}


STRUCT_AND_NAMING = [finding("oversized-function", 10), finding("magic-value", 42), finding("naming-convention", 7)]


class TestPlanSimulationTable(unittest.TestCase):
    """plan bagian 2.3 — tiap baris tabel simulasi."""

    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.info = s.load_config(RULES_DIR)

    def run_case(self, payload):
        return s.simulate(payload, self.cfg, self.info)

    def dims(self, out):
        return {k: (None if v["skipped"] else v["score"]) for k, v in out["dimension_scores"].items()}

    def test_row1_clean_one_low(self):
        # plan 2.3 baris 1: bersih, 1 temuan low → bug 98, struct 100, read 100, doc n/a → 99
        out = self.run_case(scenario(["low"], []))
        self.assertEqual(self.dims(out), {"bug": 98, "structural": 100, "readability": 100, "doc_sync": None})
        self.assertEqual(out["final_score"], 99)

    def test_row2_two_medium_struct_naming_doc_missing(self):
        # plan 2.3 baris 2: 2 medium + fungsi >50 + magic value + naming, doc tidak diupdate → 78
        out = self.run_case(scenario(["medium", "medium"], STRUCT_AND_NAMING, applicable=True, updated=False))
        self.assertEqual(self.dims(out), {"bug": 90, "structural": 80, "readability": 90, "doc_sync": 0})
        self.assertEqual(out["final_score"], 78)

    def test_row3_same_but_doc_updated(self):
        # plan 2.3 baris 3: sama dengan baris 2, doc ikut diupdate → 88
        out = self.run_case(scenario(["medium", "medium"], STRUCT_AND_NAMING, applicable=True, updated=True))
        self.assertEqual(self.dims(out)["doc_sync"], 100)
        self.assertEqual(out["final_score"], 88)

    def test_row4_claude_md_two_critical(self):
        # plan 2.3 baris 4: PR menyentuh CLAUDE.md skeleton → 2× critical agent-docs → bug 70 → 90
        payload = scenario(["critical", "critical"], [])
        payload["changed_files"] = [{"path": "CLAUDE.md", "additions": 10, "deletions": 2}]
        out = self.run_case(payload)
        self.assertEqual(self.dims(out), {"bug": 70, "structural": 100, "readability": 100, "doc_sync": None})
        self.assertEqual(out["final_score"], 90)

    def test_double_penalty_logic_error(self):
        # plan 2.2 insight 2: satu bug medium = −5 di bug DAN −10 di structural (logic-error di taksonomi v2)
        out = self.run_case(scenario(["medium"], [finding("logic-error", 30)]))
        self.assertEqual(self.dims(out)["bug"], 95)
        self.assertEqual(self.dims(out)["structural"], 90)


class TestProductionRulesConfig(unittest.TestCase):
    """Config hasil parse rules/ snapshot production 26 Okt 2026."""

    def test_snapshot_parses(self):
        cfg, info = s.load_config(RULES_DIR)
        self.assertEqual(info["source"], "rules", info.get("error"))
        self.assertEqual(cfg["deductions"]["per_finding"], 10)
        weights = {d["key"]: (d["weight"], d["enabled"]) for d in cfg["dimensions"]}
        self.assertEqual(weights, {"bug": (30, True), "structural": (30, True),
                                   "readability": (30, True), "doc_sync": (10, True)})

    def test_snapshot_taxonomy(self):
        cfg, _ = s.load_config(RULES_DIR)
        by_dim = {}
        for tx in cfg["taxonomy"]:
            by_dim.setdefault(tx["dimension"], set()).add(tx["key"])
        self.assertEqual(len(by_dim["structural"]), 17)
        self.assertEqual(by_dim["readability"], {"naming-convention", "parameter-naming", "datetime-format"})
        self.assertIn("doc-existing", by_dim["doc_sync"])
        self.assertNotIn("undocumented-api-change", by_dim["doc_sync"])

    def test_readability_text_only_categories_rejected(self):
        # Tiket KJ-C: stale-comment dijelaskan di teks tapi tidak aktif → ditolak mesin
        cfg, _ = s.load_config(RULES_DIR)
        r = s.calculate(cfg, {"findings": [finding("stale-comment", 3)]}, [GO])
        self.assertEqual(r["findings"][0]["reject_reason"], s.REJECT_UNKNOWN)

    def test_broken_rules_fall_back_to_default(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(RULES_DIR, os.path.join(tmp, "rules"))
            with open(os.path.join(tmp, "rules", "quality-score.md"), "w", encoding="utf-8") as fh:
                fh.write("tanpa front-matter\n")
            cfg, info = s.load_config(os.path.join(tmp, "rules"))
        finally:
            shutil.rmtree(tmp)
        self.assertEqual(info["source"], "default")
        self.assertEqual(cfg["deductions"]["per_finding"], 10)
        self.assertIn("front-matter", info["error"])


class TestRulesLock(unittest.TestCase):
    """rules.lock.json harus cocok dengan isi rules/*.md (konten mentah, sha256)."""

    def test_lock_matches_files(self):
        with open(os.path.join(RULES_DIR, "rules.lock.json"), encoding="utf-8") as fh:
            lock = json.load(fh)
        self.assertEqual(lock["count"], 25)
        self.assertEqual(len(lock["contexts"]), 25)
        for entry in lock["contexts"]:
            with self.subTest(entry["slug"]):
                self.assertEqual(entry["file"], entry["slug"] + ".md")
                with open(os.path.join(RULES_DIR, entry["file"]), "rb") as fh:
                    self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), entry["sha256"])


class TestRounding(unittest.TestCase):
    """math.Round Go = setengah menjauhi nol; round() Python = banker's."""

    def test_go_round(self):
        for x, want in [(0.5, 1), (1.5, 2), (2.5, 3), (88.5, 89), (-2.5, -3), (85.7, 86), (76.67, 77)]:
            with self.subTest(x):
                self.assertEqual(s.go_round(x), want)

    def test_final_half_rounds_up(self):
        # bug 95 (1 medium), struct 100, read 100, doc 0 → 8850/100 = 88.5 → Go 89 (Python round: 88)
        cfg, info = s.load_config(RULES_DIR)
        out = s.simulate(scenario(["medium"], [], applicable=True, updated=False), cfg, info)
        self.assertEqual(out["final_score"], 89)


class TestSimulateGates(unittest.TestCase):

    def setUp(self):
        self.cfg, self.info = s.load_config(RULES_DIR)

    def test_trivial_lines(self):
        payload = scenario(["critical"], [])
        payload["changed_files"] = [{"path": "a.go", "additions": 3, "deletions": 1}]
        out = s.simulate(payload, self.cfg, self.info)
        self.assertTrue(out["trivial"])
        self.assertEqual(out["gate_reasons"], ["trivial_pr"])
        self.assertIsNone(out["final_score"])

    def test_trivial_version_files_only(self):
        payload = scenario([], [])
        payload["changed_files"] = [{"path": "go.mod", "additions": 30, "deletions": 4},
                                    {"path": "go.sum", "additions": 90, "deletions": 20}]
        self.assertTrue(s.simulate(payload, self.cfg, self.info)["trivial"])

    def test_missing_quality_block_is_unscored(self):
        payload = scenario(["low"], [])
        payload["quality"] = None
        out = s.simulate(payload, self.cfg, self.info)
        self.assertEqual(out["status"], "unscored")
        self.assertIsNone(out["final_score"])

    def test_no_review_findings_key_skips_bug(self):
        payload = scenario([], [])
        del payload["findings"]
        out = s.simulate(payload, self.cfg, self.info)
        self.assertTrue(out["dimension_scores"]["bug"]["skipped"])
        self.assertEqual(out["final_score"], 100)


class TestCli(unittest.TestCase):

    def run_cli(self, payload, *args):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        try:
            json.dump(payload, tmp)
            tmp.close()
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = s.main([tmp.name, *args])
        finally:
            os.unlink(tmp.name)
        return code, buf.getvalue()

    def test_json_output(self):
        code, out = self.run_cli(scenario(["medium", "medium"], STRUCT_AND_NAMING, True, False))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["final_score"], 78)

    def test_text_output_indonesian(self):
        payload = scenario(["medium", "medium"], STRUCT_AND_NAMING + [finding("stale-comment", 9)], True, False)
        code, out = self.run_cli(payload, "--format", "text")
        self.assertEqual(code, 0)
        self.assertIn("Prediksi skor quality: 78", out)
        self.assertIn("Temuan ditolak mesin", out)
        self.assertIn("stale-comment", out)

    def test_default_config_flag(self):
        code, out = self.run_cli(scenario([], [finding("oversized-function", 1)]), "--default-config")
        self.assertEqual(json.loads(out)["config"]["source"], "default")
        self.assertEqual(json.loads(out)["dimension_scores"]["structural"]["score"], 90)

    def test_missing_changed_files_is_error(self):
        payload = scenario([], [])
        del payload["changed_files"]
        err = io.StringIO()
        with redirect_stderr(err):
            code, _ = self.run_cli(payload)
        self.assertEqual(code, 2)
        self.assertIn("changed_files", err.getvalue())

    def test_example_input_file(self):
        with open(os.path.join(SCRIPTS_DIR, "example-input.json"), encoding="utf-8") as fh:
            code, out = self.run_cli(json.load(fh))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["final_score"], 78)


if __name__ == "__main__":
    unittest.main()
