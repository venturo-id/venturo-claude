"""Test vector yang diturunkan 1:1 dari test Go kinerja-be (production @ da582b1e).

Tiap test menyebut asal vector-nya: file `_test.go` dan nama fungsi test Go.
Path relatif terhadap root kinerja-be.
"""
import copy
import unittest

from _helpers import base_block, set_enabled, simulate_score as s

CALC = "internal/modules/review/quality_score/domain/calculate_test.go"


def calc(block, files=("src/a.go",), bug_score=None, cfg=None):
    return s.calculate(cfg or s.default_config(), block, list(files), bug_score)


class TestFromSeverities(unittest.TestCase):
    """internal/shared/reviewscore/score_test.go — TestFromSeverities (tabel 8 kasus)."""

    CASES = [
        ("clean", [], 100),
        ("one critical", ["critical"], 85),
        ("critical plus two high", ["critical", "high", "high"], 65),
        ("medium and low", ["medium", "low", "low"], 91),
        ("info is free", ["info"], 100),
        ("unknown severity is free", ["showstopper"], 100),
        ("case insensitive", ["CRITICAL", "High"], 75),
        ("floors at zero", ["critical"] * 7, 0),
    ]

    def test_table(self):
        for name, severities, want in self.CASES:
            with self.subTest(name):
                self.assertEqual(s.from_severities(severities), want)

    def test_pooled_weights(self):
        # score_test.go TestFromBodiesPoolsAcrossReviewTypes (100-10-5-2) dan
        # TestFromBodyGrades (100-15-5): pooling severity lintas review type.
        self.assertEqual(s.from_severities(["high", "medium", "low"]), 83)
        self.assertEqual(s.from_severities(["critical", "medium"]), 80)


class TestIsTrivial(unittest.TestCase):
    """internal/modules/review/quality_score/domain/trivial_test.go — TestIsTrivial (9 kasus)."""

    CASES = [
        ("3 baris file kode", 3, ["src/a.go"], True),
        ("4 baris tepat di bawah ambang", 4, ["src/a.go"], True),
        ("5 baris file kode = tidak trivial", 5, ["src/a.go"], False),
        ("20 baris hanya package.json", 20, ["package.json"], True),
        ("20 baris pubspec di subfolder", 20, ["apps/mobile/pubspec.yaml", "apps/mobile/pubspec.lock"], True),
        ("20 baris package.json + kode", 20, ["package.json", "src/a.go"], False),
        ("20 baris files kosong = tidak tahu", 20, None, False),
        ("0 baris files kosong = trivial lewat aturan baris", 0, None, True),
        ("basename case-sensitive", 20, ["Package.json"], False),
    ]

    def test_table(self):
        for name, lines, files, want in self.CASES:
            with self.subTest(name):
                self.assertEqual(s.is_trivial(lines, files), want)


class TestCalculate(unittest.TestCase):
    """CALC — skor quality dengan DefaultConfig (PerFinding 15)."""

    def test_happy_path(self):
        # CALC TestCalculateHappyPath: structural 85, readability 85, final 85; bug & doc_sync skip.
        r = calc(base_block())
        self.assertEqual(r["status"], "scored")
        self.assertEqual(r["final_score"], 85)
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 85)
        self.assertEqual(r["dimension_scores"]["readability"]["score"], 85)
        self.assertTrue(r["dimension_scores"]["doc_sync"]["skipped"])
        self.assertTrue(r["dimension_scores"]["bug"]["skipped"])

    def test_reject_unknown_category_and_evidence(self):
        # CALC TestRejectUnknownCategoryAndEvidence
        block = dict(base_block(), findings=[
            {"category": "kategori-karangan", "evidence": "src/a.go:1"},
            {"category": "oversized-function", "evidence": "src/tidak-diubah.go:5"},
            {"category": "oversized-function", "evidence": "tanpa-line"},
        ])
        r = calc(block)
        self.assertTrue(all(f["rejected"] for f in r["findings"]))
        self.assertEqual([f["reject_reason"] for f in r["findings"]],
                         [s.REJECT_UNKNOWN, s.REJECT_EVIDENCE, s.REJECT_EVIDENCE])
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 100)

    def test_doc_sync_applicable_not_updated_is_zero(self):
        # CALC TestDocSyncApplicable
        block = dict(base_block(), doc_sync_applicable=True, doc_sync_updated=False)
        ds = calc(block)["dimension_scores"]["doc_sync"]
        self.assertFalse(ds["skipped"])
        self.assertEqual(ds["score"], 0)

    def test_all_dimensions_disabled_is_unscored(self):
        # CALC TestReallocationAllDimensionsSkipped + TestAllDimensionsSkippedIsUnscored
        cfg = s.default_config()
        for d in cfg["dimensions"]:
            d["enabled"] = False
        r = calc(base_block(), cfg=cfg)
        self.assertEqual(r["status"], "unscored")
        self.assertEqual(r["final_score"], 0)

    def test_deduction_clamps_at_zero(self):
        # CALC TestDeductionClampsAtZero: 13 × 15 = 195 → clamp 0
        block = dict(base_block(), findings=[
            {"category": "oversized-function", "evidence": "src/a.go:%d" % i} for i in range(1, 14)])
        self.assertEqual(calc(block)["dimension_scores"]["structural"]["score"], 0)

    def test_reject_category_not_in_configured_taxonomy(self):
        # CALC TestRejectCategoryNotInConfiguredTaxonomy
        cfg = s.default_config()
        cfg["taxonomy"] = [tx for tx in cfg["taxonomy"] if tx["key"] != "oversized-function"]
        block = dict(base_block(), findings=[{"category": "oversized-function", "evidence": "src/a.go:10"}])
        r = calc(block, cfg=cfg)
        self.assertTrue(r["findings"][0]["rejected"])
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 100)

    def test_empty_findings(self):
        # CALC TestEmptyFindingsList
        r = calc(dict(base_block(), findings=None))
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 100)
        self.assertEqual(r["dimension_scores"]["readability"]["score"], 100)

    def test_nil_block_is_unscored(self):
        # CALC TestNilBlockIsUnscored + TestCalculateDeductionZeroWhenUnscored
        r = calc(None)
        self.assertEqual(r["status"], "unscored")
        self.assertEqual(r["final_score"], 0)
        self.assertEqual(r["findings"], [])

    def test_zero_per_finding_falls_back_to_default(self):
        # CALC TestZeroDeductionsFallsBackToDefaultNotFreeScore
        cfg = s.default_config()
        cfg["deductions"] = {"per_finding": 0, "normalize_per_lines": 0}
        r = calc(base_block(), cfg=cfg)
        self.assertNotEqual(r["final_score"], 100)
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 85)

    def test_disabled_dimension_dropped(self):
        # CALC TestDisabledDimensionDroppedFromResultAndFindings
        cfg = s.default_config()
        set_enabled(cfg, "readability", False)
        cfg["dimensions"][1]["weight"] += 40
        block = base_block()
        block["findings"].append({"category": "naming-convention", "evidence": "src/a.go:7"})
        r = calc(block, cfg=cfg)
        self.assertNotIn("readability", r["dimension_scores"])
        self.assertFalse(any(f["category"] == "naming-convention" for f in r["findings"]))
        self.assertEqual(len(r["dropped"]), 2)

    def test_no_hard_gate(self):
        # CALC TestNoHardGateCapAfterRemoval
        block = base_block()
        block["findings"].append({"category": "excessive-complexity", "evidence": "src/a.go:7"})
        r = calc(block)
        self.assertEqual(r["status"], "scored")
        self.assertEqual(r["gate_reasons"], [])

    def test_readability_deduction_based(self):
        # CALC TestCalculateReadabilityDeductionBased
        block = {"findings": [{"category": "naming-convention", "evidence": "a.go:10", "note": "n"}]}
        r = calc(block, files=["a.go"])
        self.assertEqual(r["dimension_scores"]["readability"]["score"], 85)
        self.assertFalse(r["dimension_scores"]["readability"]["skipped"])
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 100)

    def test_doc_sync_findings_do_not_deduct(self):
        # CALC TestCalculateDocSyncFindingsDoNotDeduct: final 86 (6000/70 = 85.7)
        block = {"doc_sync_applicable": True, "doc_sync_updated": False, "findings": [
            {"category": c, "evidence": "a.go:%d" % n, "note": "n"}
            for c, n in [("undocumented-api-change", 10), ("stale-api-doc", 12), ("missing-changelog-entry", 14)]]}
        r = calc(block, files=["a.go"])
        self.assertFalse(any(f["rejected"] for f in r["findings"]))
        self.assertEqual(r["dimension_scores"]["doc_sync"]["score"], 0)
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 100)
        self.assertEqual(r["dimension_scores"]["readability"]["score"], 100)
        self.assertEqual(r["final_score"], 86)

    def test_doc_sync_finding_rejected_when_not_applicable(self):
        # CALC TestCalculateDocSyncFindingRejectedWhenNotApplicable
        block = {"doc_sync_applicable": False,
                 "findings": [{"category": "undocumented-api-change", "evidence": "a.go:10"}]}
        r = calc(block, files=["a.go"])
        self.assertEqual(len(r["findings"]), 1)
        self.assertEqual(r["findings"][0]["reject_reason"], s.REJECT_DOC_SYNC_NA)
        self.assertTrue(r["dimension_scores"]["doc_sync"]["skipped"])

    def test_no_findings_scores_100(self):
        # CALC TestCalculateIgnoresAIDimensionScores
        r = calc({"findings": None}, files=["a.go"])
        self.assertEqual(r["final_score"], 100)
        self.assertTrue(r["dimension_scores"]["doc_sync"]["skipped"])

    def test_legacy_dimension_skipped_not_zero(self):
        # CALC TestCalculateLegacyDimensionSkippedNotZero
        cfg = s.default_config()
        cfg["dimensions"].append(s.dimension("correctness", 30, 3))
        r = calc({"findings": None}, files=["a.go"], cfg=cfg)
        self.assertTrue(r["dimension_scores"]["correctness"]["skipped"])
        self.assertEqual(r["final_score"], 100)
        self.assertEqual(r["status"], "scored")

    def test_duplicate_deducts_once(self):
        # CALC TestDuplicateFindingDeductsOnce
        block = dict(base_block(), findings=[
            {"category": "oversized-function", "evidence": "src/a.go:10", "note": "draft"},
            {"category": "oversized-function", "evidence": "src/a.go:10", "note": "verifikator menulis ulang"},
        ])
        r = calc(block)
        self.assertEqual(r["dimension_scores"]["structural"]["score"], 85)
        self.assertEqual(len(r["findings"]), 2)
        self.assertFalse(r["findings"][0]["rejected"])
        self.assertEqual(r["findings"][1]["reject_reason"], s.REJECT_DUPLICATE)

    def test_same_category_different_evidence_both_deduct(self):
        # CALC TestSameCategoryDifferentEvidenceBothDeduct
        block = dict(base_block(), findings=[
            {"category": "oversized-function", "evidence": "src/a.go:10"},
            {"category": "oversized-function", "evidence": "src/a.go:120"},
        ])
        self.assertEqual(calc(block)["dimension_scores"]["structural"]["score"], 70)

    def test_deduction_per_finding_and_contribution(self):
        # CALC TestCalculateDeductionPerFinding: final 87, contribution 21/30/10/26.4
        block = {"doc_sync_applicable": True, "doc_sync_updated": True, "findings": [
            {"category": "oversized-function", "evidence": "src/a.go:10"},
            {"category": "excessive-complexity", "evidence": "src/a.go:40"},
            {"category": "oversized-function", "evidence": "src/tidak-diubah.go:5"},
        ]}
        r = calc(block, bug_score=88)
        dims = r["dimension_scores"]
        self.assertEqual(r["final_score"], 87)
        self.assertEqual(dims["structural"]["deduction"], 30)
        self.assertEqual(dims["readability"]["deduction"], 0)
        self.assertEqual(dims["bug"]["score"], 88)
        self.assertEqual([f["deduction"] for f in r["findings"]], [15.0, 15.0, 0.0])
        want = {"structural": 21, "readability": 30, "doc_sync": 10, "bug": 26.4}
        self.assertEqual({k: v["contribution"] for k, v in dims.items()}, want)

    def test_bug_dimension_pulls_final_down(self):
        # CALC TestCalculateBugDimensionSkippedWithoutScore: (85*30+85*30+60*30)/90 = 76.67 → 77
        without = calc(base_block())
        with_bug = calc(base_block(), bug_score=60)
        self.assertTrue(without["dimension_scores"]["bug"]["skipped"])
        self.assertEqual(with_bug["dimension_scores"]["bug"]["score"], 60)
        self.assertEqual(with_bug["final_score"], 77)

    def test_contributions_sum_to_final(self):
        # CALC TestCalculateContributionsSumToFinal (small/mixed)
        mixed = dict(base_block(), doc_sync_applicable=True, doc_sync_updated=True)
        for block in (base_block(), mixed):
            r = calc(block)
            total = sum(d["contribution"] for d in r["dimension_scores"].values() if not d["skipped"])
            self.assertLessEqual(abs(total - r["final_score"]), 1)
            for d in r["dimension_scores"].values():
                self.assertEqual("contribution" in d, not d["skipped"])

    def test_doc_sync_finding_has_zero_deduction(self):
        # CALC TestCalculateDeductionZeroForDocSyncFinding
        def block(with_doc):
            findings = [{"category": "oversized-function", "evidence": "src/a.go:10"}]
            if with_doc:
                findings.append({"category": "stale-api-doc", "evidence": "docs/api.md:1"})
            return {"findings": findings, "doc_sync_applicable": True, "doc_sync_updated": True}
        files = ["docs/api.md", "src/a.go"]
        base, r = calc(block(False), files=files), calc(block(True), files=files)
        doc = [f for f in r["findings"] if f["category"] == "stale-api-doc"][0]
        self.assertFalse(doc["rejected"])
        self.assertEqual(doc["deduction"], 0.0)
        self.assertEqual(r["final_score"], base["final_score"])

    def test_contribution_uses_effective_weight(self):
        # CALC TestCalculateContributionUsesEffectiveWeight: 85 × 30/60 = 42.5
        self.assertEqual(calc(base_block())["dimension_scores"]["structural"]["contribution"], 42.5)


class TestConfigValidate(unittest.TestCase):
    """internal/modules/review/quality_score/domain/config_test.go."""

    def assert_invalid(self, cfg, needle):
        with self.assertRaises(s.RulesError) as ctx:
            s.validate_config(cfg)
        self.assertIn(needle, str(ctx.exception))

    def test_default_valid(self):
        # config_test.go TestDefaultConfigValid + TestValidateDisabledExcludedFromSum
        s.validate_config(s.default_config())

    def test_weight_sum(self):
        # config_test.go TestValidateWeightSum
        cfg = s.default_config()
        cfg["dimensions"][0]["weight"] += 5
        self.assert_invalid(cfg, "weight")

    def test_duplicate_taxonomy(self):
        # config_test.go TestValidateDuplicateTaxonomy
        cfg = s.default_config()
        cfg["taxonomy"].append(copy.deepcopy(cfg["taxonomy"][0]))
        self.assert_invalid(cfg, "taxonomy")

    def test_duplicate_dimension(self):
        # config_test.go TestValidateDuplicateDimension
        cfg = s.default_config()
        cfg["dimensions"].append(s.dimension("doc_sync", 0, 1, enabled=False))
        self.assert_invalid(cfg, "duplikat")

    def test_taxonomy_unknown_dimension(self):
        # config_test.go TestValidateTaxonomyDimension
        cfg = s.default_config()
        cfg["taxonomy"][0]["dimension"] = "bukan-dimensi"
        self.assert_invalid(cfg, "tidak dikenal")

    def test_removed_dimension(self):
        # config_test.go TestValidateRejectsRemovedDimension
        cfg = s.default_config()
        cfg["dimensions"].append(s.dimension("correctness", 0, 3, enabled=False))
        self.assert_invalid(cfg, "tidak dikenal")

    def test_zero_normalize_per_lines_ok(self):
        # config_test.go TestValidateAllowsZeroNormalizePerLines
        cfg = s.default_config()
        cfg["deductions"]["normalize_per_lines"] = 0
        s.validate_config(cfg)


def valid_files():
    """validFiles() di md_rules_test.go."""
    return {
        "quality-score": "---\nper_finding: 15\nnormalize_per_lines: 100\n---\nIntro aturan.\n",
        "quality-score/structural": "---\nweight: 30\ntier: 2\nenabled: true\ncategories:\n"
                                    "  - oversized-function\n  - deep-nesting\n---\nPanduan structural.\n",
        "quality-score/readability": "---\nweight: 30\ntier: 3\nenabled: true\ncategories:\n"
                                     "  - naming-convention\n---\nPanduan readability.\n",
        "quality-score/doc-sync": "---\nweight: 10\ntier: 1\nenabled: true\nconditional: true\ncategories:\n"
                                  "  - stale-api-doc\n---\nPanduan doc sync.\n",
        "quality-score/bug": "---\nweight: 30\ntier: 1\nenabled: true\n---\nSkor bug dari code review.\n",
    }


class TestParseRulesContexts(unittest.TestCase):
    """internal/modules/review/quality_score/domain/md_rules_test.go."""

    def test_builds_config_and_markdown(self):
        # md_rules_test.go TestParseRulesContextsBuildsConfigAndMarkdown
        cfg, md = s.parse_rules_contexts(valid_files())
        self.assertEqual(cfg["deductions"], {"per_finding": 15, "normalize_per_lines": 100})
        self.assertEqual([d["key"] for d in cfg["dimensions"]], ["structural", "readability", "doc_sync", "bug"])
        self.assertEqual(cfg["dimensions"][0]["weight"], 30)
        self.assertTrue(cfg["dimensions"][2]["conditional"])
        tax = s.taxonomy_by_key(cfg)
        self.assertEqual(tax["deep-nesting"]["dimension"], "structural")
        self.assertEqual(tax["stale-api-doc"]["dimension"], "doc_sync")
        self.assertTrue(md.startswith("Intro aturan."))
        self.assertNotIn("per_finding", md)
        self.assertLess(md.index("Panduan structural."), md.index("Panduan readability."))

    def test_rejects_broken_input(self):
        # md_rules_test.go TestParseRulesContextsRejectsBrokenInput (7 mutasi)
        mutations = {
            "slug hilang": lambda f: f.pop("quality-score/readability"),
            "tanpa front matter": lambda f: f.update({"quality-score": "cuma badan"}),
            "yaml rusak": lambda f: f.update({"quality-score/structural": "---\nweight: [\n---\nx"}),
            "bobot tidak 100": lambda f: f.update({"quality-score/structural":
                                                   f["quality-score/structural"].replace("weight: 30", "weight: 29", 1)}),
            "weight tidak diisi": lambda f: f.update({"quality-score/doc-sync":
                                                      "---\ntier: 1\nenabled: true\ncategories:\n  - x\n---\nb"}),
            "dimensi aktif tanpa kategori": lambda f: f.update({"quality-score/readability":
                                                                "---\nweight: 30\ntier: 3\nenabled: true\n---\nb"}),
            "slug bug hilang": lambda f: f.pop("quality-score/bug"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                files = valid_files()
                mutate(files)
                with self.assertRaises(s.RulesError):
                    s.parse_rules_contexts(files)

    def test_scoring_without_normalize_per_lines(self):
        # md_rules_test.go TestParseScoringWithoutNormalizePerLines
        files = valid_files()
        files["quality-score"] = "---\nper_finding: 10\n---\nIntro aturan.\n"
        cfg, _ = s.parse_rules_contexts(files)
        self.assertEqual(cfg["deductions"]["per_finding"], 10)


if __name__ == "__main__":
    unittest.main()
