#!/usr/bin/env python3
"""Sinkronkan rules/ dengan context review aktif di Kinerja production.

    KINERJA_API_KEY=... sync_from_kinerja.py [--summary FILE] [--no-bump]

Sampai endpoint export KJ-G tersedia, script memakai endpoint kinerja-be yang sudah ada:
GET /review/v1/contexts (slug + id versi aktif), lalu GET /review/v1/contexts/:id per slug
(konten mentah, front-matter ikut, placeholder belum dirender). Auth: header X-API-Key,
key butuh izin review:context:view. Base URL dari KINERJA_API_URL
(default https://kinerja-api.venturo.id).

Perubahan dideteksi dari sha256 konten dan metadata, bukan nomor versi (kj-399 menambal
isi tanpa menaikkan versi). Bila ada perubahan: rules/<slug>.md ditulis apa adanya, file
slug yang tidak aktif lagi dihapus, rules.lock.json ditulis ulang, versi plugin dan
marketplace naik patch, ringkasan markdown ditulis ke --summary. Tanpa perubahan, tidak
ada file yang disentuh dan --summary tidak dibuat.
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPTS_DIR)
ROOT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
PLUGIN_NAME = "venturo-kinerja"
DEFAULT_API_URL = "https://kinerja-api.venturo.id"
TIMEOUT_SECONDS = 30
# Sama dengan slugPattern kinerja-be (context.service.go). Slug dipakai sebagai path file;
# pola ini menolak "..", path absolut, dan segmen kosong.
SLUG_RE = re.compile(r"[a-z0-9_-]{1,64}(/[a-z0-9_-]{1,64})?")
LOCK_FIELDS = ("category", "skill_type", "version", "description")


class SyncError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Jangan ikuti redirect: urllib akan membawa X-API-Key ke host/skema tujuan."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 3xx jadi HTTPError


def api_fetcher(base_url, api_key):
    """fetch(path) → field `data` dari envelope response kinerja-be."""
    parsed = urllib.parse.urlparse(base_url)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise SyncError("KINERJA_API_URL harus https (http hanya untuk localhost): %s" % base_url)
    prefix = base_url.rstrip("/") + "/review/v1"
    opener = urllib.request.build_opener(_NoRedirect)

    def fetch(path):
        req = urllib.request.Request(prefix + path, headers={
            "X-API-Key": api_key, "Accept": "application/json", "User-Agent": "venturo-kinerja-sync"})
        try:
            with opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as err:
            err.close()
            hint = " (cek API key dan izin review:context:view)" if err.code in (401, 403) else ""
            raise SyncError("GET %s gagal: HTTP %d%s" % (path, err.code, hint)) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            raise SyncError("GET %s gagal: %s" % (path, err)) from None
        if not isinstance(body, dict) or "data" not in body:
            raise SyncError("GET %s: response tanpa field data" % path)
        return body["data"]

    return fetch


def fetch_active(fetch):
    """Konten penuh versi aktif + approved untuk tiap slug, urut slug."""
    listing = fetch("/contexts")
    out = []
    for entry in listing.get("contexts") or []:
        active = entry.get("active")
        if not active:
            continue  # slug yang baru punya versi pending
        slug = entry.get("slug", "")
        if not SLUG_RE.fullmatch(slug):
            raise SyncError("slug tidak valid dari API: %r" % slug)
        full = fetch("/contexts/" + urllib.parse.quote(str(active["id"]), safe=""))
        # Versi aktif bisa berganti di antara dua request; gagal saja, jadwal berikut mengulang.
        if full.get("slug") != slug or not full.get("is_active") or full.get("status") != "approved":
            raise SyncError("context %s berubah saat sync (id %s); ulangi" % (slug, active["id"]))
        out.append(full)
    if not out:
        raise SyncError("API tidak mengembalikan context aktif; rules lama dibiarkan")
    return sorted(out, key=lambda c: c["slug"])


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def file_sha256(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None


def lock_entry(full):
    raw = full["content"].encode("utf-8")
    return {
        "slug": full["slug"],
        "file": full["slug"] + ".md",
        "category": full.get("category", ""),
        "skill_type": full.get("skill_type", ""),
        "version": full.get("version"),
        "description": full.get("description") or "",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "active_updated_at": full.get("updated_at", ""),
    }


def diff_rows(old, new, out_dir):
    """Baris ringkasan per slug yang berubah: (slug, jenis, versi, sha)."""
    rows = []
    for slug in sorted(set(old) | set(new)):
        o, n = old.get(slug), new.get(slug)
        if n is None:
            rows.append((slug, "dihapus", str(o["version"]), o["sha256"][:8]))
            continue
        on_disk = file_sha256(os.path.join(out_dir, n["file"]))
        if o is None:
            rows.append((slug, "baru", str(n["version"]), n["sha256"][:8]))
        elif on_disk != n["sha256"] or o["sha256"] != n["sha256"]:
            kind = "isi berubah" if o["version"] != n["version"] else "isi berubah, versi tetap"
            rows.append((slug, kind, "%s → %s" % (o["version"], n["version"]),
                         "%s → %s" % (o["sha256"][:8], n["sha256"][:8])))
        elif any(o.get(k) != n[k] for k in LOCK_FIELDS):
            fields = ", ".join(k for k in LOCK_FIELDS if o.get(k) != n[k])
            rows.append((slug, "metadata: " + fields, "%s → %s" % (o["version"], n["version"]),
                         n["sha256"][:8]))
    return rows


def summary_markdown(rows):
    lines = ["## Sync rules Kinerja", "",
             "Sumber: context aktif Kinerja (`GET /review/v1/contexts`).", "",
             "| Slug | Perubahan | Versi | sha256 |", "|---|---|---|---|"]
    lines += ["| `%s` | %s | %s | `%s` |" % row for row in rows]
    return "\n".join(lines) + "\n"


def bump_patch(version):
    major, minor, patch = (int(p) for p in version.split("."))
    return "%d.%d.%d" % (major, minor, patch + 1)


def bump_versions(plugin_json, marketplace_json):
    plugin = read_json(plugin_json)
    plugin["version"] = bump_patch(plugin["version"])
    write_json(plugin_json, plugin)
    market = read_json(marketplace_json)
    entries = [p for p in market["plugins"] if p["name"] == PLUGIN_NAME]
    if len(entries) != 1:
        raise SyncError("entri %s di marketplace.json tidak ditemukan" % PLUGIN_NAME)
    entries[0]["version"] = plugin["version"]
    market["metadata"]["version"] = bump_patch(market["metadata"]["version"])
    write_json(marketplace_json, market)
    return plugin["version"], market["metadata"]["version"]


def remove_file(out_dir, rel):
    path = os.path.join(out_dir, rel)
    if os.path.exists(path):
        os.remove(path)
    parent = os.path.dirname(path)
    if parent != out_dir and os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)


def sync(contexts, out_dir, now, api_url=DEFAULT_API_URL, plugin_json=None, marketplace_json=None):
    """Tulis rules dari `contexts` (hasil fetch_active). Return ringkasan, atau None bila sama."""
    lock_path = os.path.join(out_dir, "rules.lock.json")
    lock = read_json(lock_path)
    old = {c["slug"]: c for c in lock["contexts"]}
    entries = [lock_entry(c) for c in contexts]
    new = {e["slug"]: e for e in entries}
    rows = diff_rows(old, new, out_dir)
    if not rows:
        return None

    for full, entry in zip(contexts, entries):
        path = os.path.join(out_dir, entry["file"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(full["content"].encode("utf-8"))
    for slug in set(old) - set(new):
        remove_file(out_dir, old[slug]["file"])

    lock["source"] = dict(lock.get("source", {}), url=api_url.rstrip("/") + "/review/v1/contexts",
                          method="api-sync",
                          note="Konten mentah versi aktif dari GET /review/v1/contexts/:id "
                               "(scripts/sync_from_kinerja.py); dibandingkan lewat sha256.")
    lock["synced_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lock["count"] = len(entries)
    lock["contexts"] = entries
    write_json(lock_path, lock)

    summary = summary_markdown(rows)
    if plugin_json and marketplace_json:
        plugin_version, market_version = bump_versions(plugin_json, marketplace_json)
        summary += "\nVersi: %s %s, marketplace %s.\n" % (PLUGIN_NAME, plugin_version, market_version)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join(PLUGIN_DIR, "rules"), help="folder rules/")
    ap.add_argument("--summary", help="tulis ringkasan markdown ke file ini bila ada perubahan")
    ap.add_argument("--no-bump", action="store_true", help="jangan naikkan versi plugin/marketplace")
    args = ap.parse_args(argv)

    api_key = os.environ.get("KINERJA_API_KEY", "")
    if not api_key:
        print("KINERJA_API_KEY belum di-set", file=sys.stderr)
        return 2
    try:
        api_url = os.environ.get("KINERJA_API_URL") or DEFAULT_API_URL
        fetch = api_fetcher(api_url, api_key)
        contexts = fetch_active(fetch)
        bump = (None, None) if args.no_bump else (
            os.path.join(PLUGIN_DIR, ".claude-plugin", "plugin.json"),
            os.path.join(ROOT_DIR, ".claude-plugin", "marketplace.json"))
        summary = sync(contexts, os.path.abspath(args.out), _dt.datetime.now(_dt.timezone.utc),
                       api_url, *bump)
    except (SyncError, KeyError, OSError) as err:
        print("sync gagal: %s" % err, file=sys.stderr)
        return 1
    if summary is None:
        print("Tidak ada perubahan: rules sama dengan Kinerja production.")
        return 0
    print(summary)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
