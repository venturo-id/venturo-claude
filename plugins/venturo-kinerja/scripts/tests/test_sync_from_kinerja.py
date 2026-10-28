"""Test sync_from_kinerja.py: API palsu, folder rules sementara (salinan snapshot asli)."""
import datetime as dt
import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest

from _helpers import RULES_DIR

import sync_from_kinerja as sync_mod

NOW = dt.datetime(2026, 10, 28, 1, 0, tzinfo=dt.timezone.utc)


def snapshot_contexts():
    """Response API yang setara dengan snapshot rules/ saat ini (tanpa perubahan)."""
    with open(os.path.join(RULES_DIR, "rules.lock.json"), encoding="utf-8") as fh:
        lock = json.load(fh)
    out = []
    for i, e in enumerate(lock["contexts"]):
        with open(os.path.join(RULES_DIR, e["file"]), encoding="utf-8") as fh:
            content = fh.read()
        out.append({"id": "id-%d" % i, "slug": e["slug"], "content": content, "category": e["category"],
                    "skill_type": e["skill_type"], "status": "approved", "version": e["version"],
                    "is_active": True, "description": e["description"] or None,
                    "updated_at": e["active_updated_at"]})
    return out


def fake_fetch(contexts, pending_only=()):
    by_id = {c["id"]: c for c in contexts}
    listing = [{"slug": c["slug"], "active": {"id": c["id"], "version": c["version"]}} for c in contexts]
    listing += [{"slug": s, "active": None, "pending": {"id": "p", "version": 1}} for s in pending_only]

    def fetch(path):
        if path == "/contexts":
            return {"contexts": listing}
        return by_id[path[len("/contexts/"):]]

    return fetch


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.rules = os.path.join(self.tmp, "rules")
        shutil.copytree(RULES_DIR, self.rules)
        self.plugin_json = os.path.join(self.tmp, "plugin.json")
        self.market_json = os.path.join(self.tmp, "marketplace.json")
        sync_mod.write_json(self.plugin_json, {"name": "venturo-kinerja", "version": "0.1.1"})
        sync_mod.write_json(self.market_json, {"metadata": {"version": "1.0.17"}, "plugins": [
            {"name": "venturo-arsenal", "version": "1.0.1"}, {"name": "venturo-kinerja", "version": "0.1.1"}]})

    def run_sync(self, contexts):
        fetched = sync_mod.fetch_active(fake_fetch(contexts))
        return sync_mod.sync(fetched, self.rules, NOW, plugin_json=self.plugin_json,
                             marketplace_json=self.market_json)

    def lock(self):
        return sync_mod.read_json(os.path.join(self.rules, "rules.lock.json"))

    def by_slug(self, contexts, slug):
        return next(c for c in contexts if c["slug"] == slug)


class TestSync(SyncTestCase):
    def test_no_change_touches_nothing(self):
        before = self.lock()
        self.assertIsNone(self.run_sync(snapshot_contexts()))
        self.assertEqual(self.lock(), before)
        self.assertEqual(sync_mod.read_json(self.plugin_json)["version"], "0.1.1")

    def test_content_change_without_version_bump_is_detected(self):
        ctxs = snapshot_contexts()
        laporan = self.by_slug(ctxs, "laporan")
        laporan["content"] += "\nbaris baru\n"
        summary = self.run_sync(ctxs)
        self.assertIn("| `laporan` | isi berubah, versi tetap | 15 → 15 |", summary)
        with open(os.path.join(self.rules, "laporan.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), laporan["content"])
        entry = next(e for e in self.lock()["contexts"] if e["slug"] == "laporan")
        self.assertEqual(entry["bytes"], len(laporan["content"].encode("utf-8")))
        self.assertEqual(self.lock()["synced_at"], "2026-10-28T01:00:00Z")
        self.assertEqual(self.lock()["source"]["method"], "api-sync")

    def test_version_bumps_plugin_and_marketplace(self):
        ctxs = snapshot_contexts()
        self.by_slug(ctxs, "workflow").update(version=13, content="baru\n")
        summary = self.run_sync(ctxs)
        self.assertIn("| `workflow` | isi berubah | 12 → 13 |", summary)
        self.assertEqual(sync_mod.read_json(self.plugin_json)["version"], "0.1.2")
        market = sync_mod.read_json(self.market_json)
        self.assertEqual(market["metadata"]["version"], "1.0.18")
        self.assertEqual([p["version"] for p in market["plugins"]], ["1.0.1", "0.1.2"])

    def test_new_and_removed_slugs(self):
        ctxs = [c for c in snapshot_contexts() if not c["slug"].startswith("php")]
        ctxs.append({"id": "new", "slug": "rust", "content": "# Rust\n", "category": "stack",
                     "skill_type": "dynamic", "status": "approved", "version": 1, "is_active": True,
                     "description": None, "updated_at": "2026-10-28T00:00:00Z"})
        summary = self.run_sync(ctxs)
        self.assertIn("| `rust` | baru | 1 |", summary)
        self.assertIn("| `php/laravel` | dihapus | 1 |", summary)
        self.assertFalse(os.path.exists(os.path.join(self.rules, "php")))
        self.assertTrue(os.path.exists(os.path.join(self.rules, "rust.md")))
        lock = self.lock()
        self.assertEqual(lock["count"], len(ctxs))
        self.assertEqual([e["slug"] for e in lock["contexts"]], sorted(c["slug"] for c in ctxs))

    def test_metadata_only_change(self):
        ctxs = snapshot_contexts()
        self.by_slug(ctxs, "golang")["skill_type"] = "required"
        self.assertIn("| `golang` | metadata: skill_type |", self.run_sync(ctxs))

    def test_lock_written_by_sync_matches_files(self):
        ctxs = snapshot_contexts()
        self.by_slug(ctxs, "react")["content"] = "isi react ✓\n"
        self.run_sync(ctxs)
        for e in self.lock()["contexts"]:
            self.assertEqual(sync_mod.file_sha256(os.path.join(self.rules, e["file"])), e["sha256"])


class TestFetchActive(SyncTestCase):
    def test_skips_pending_only_slugs(self):
        ctxs = snapshot_contexts()
        got = sync_mod.fetch_active(fake_fetch(ctxs, pending_only=["draft-baru"]))
        self.assertEqual(len(got), len(ctxs))

    def test_rejects_path_traversal_slug(self):
        for slug in ("../evil", "/abs", "a//b", "A", "a/"):
            with self.subTest(slug):
                ctxs = snapshot_contexts()[:1]
                ctxs[0]["slug"] = slug
                with self.assertRaises(sync_mod.SyncError):
                    sync_mod.fetch_active(fake_fetch(ctxs))

    def test_rejects_row_that_is_no_longer_active(self):
        ctxs = snapshot_contexts()
        ctxs[0]["is_active"] = False
        with self.assertRaises(sync_mod.SyncError):
            sync_mod.fetch_active(fake_fetch(ctxs))

    def test_empty_listing_keeps_old_rules(self):
        with self.assertRaises(sync_mod.SyncError):
            sync_mod.fetch_active(fake_fetch([]))


class _Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        _Handler.seen.append((self.path, self.headers.get("X-API-Key")))
        if self.headers.get("X-API-Key") != "k":
            self.send_response(401)
            self.end_headers()
            return
        body = json.dumps({"message": "OK", "data": {"contexts": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestApiFetcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_sends_x_api_key_and_unwraps_data(self):
        self.assertEqual(sync_mod.api_fetcher(self.base, "k")("/contexts"), {"contexts": []})
        self.assertIn(("/review/v1/contexts", "k"), _Handler.seen)

    def test_unauthorized_has_hint_and_no_key(self):
        with self.assertRaises(sync_mod.SyncError) as cm:
            sync_mod.api_fetcher(self.base, "rahasia")("/contexts")
        self.assertIn("HTTP 401", str(cm.exception))
        self.assertIn("review:context:view", str(cm.exception))
        self.assertNotIn("rahasia", str(cm.exception))

    def test_refuses_plain_http_to_remote_host(self):
        with self.assertRaises(sync_mod.SyncError):
            sync_mod.api_fetcher("http://kinerja-api.venturo.id", "k")


if __name__ == "__main__":
    unittest.main()
