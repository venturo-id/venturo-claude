"""Stop — pengingat doc-sync: kode API/route/dto/migration berubah tanpa dokumen.

Sekali per keadaan diff (diff_hash disimpan di .claude/venturo-kinerja/), dan
tidak pernah saat stop_hook_active, supaya tidak berputar. Mengembalikan
decision "block" dengan alasan, jadi Claude sempat memperbarui dokumen atau
menjelaskan ke engineer kenapa tidak perlu.
"""

import os

from _common import emit, guarded, lib, project_dir, supported

import kinerja_status as ks

REMINDED = os.path.join(ks.STATE_DIR, "doc-sync-reminded")


def pending_docs(repo):
    ref, merge_base = ks.resolve_base(repo, None)
    files = ks.changed_files(repo, merge_base)
    paths = [f["path"] for f in files]
    doc = lib.doc_sync_check(paths, {st["id"] for st in lib.detect_stacks(repo)} or None)
    items = list(doc["missing"])
    code_changed = any(not (p.startswith("docs/") or p.endswith(".md")) for p in paths)
    if os.path.isfile(os.path.join(repo, "CHANGELOG.md")) and code_changed and not doc["changelog_updated"]:
        items.append("CHANGELOG.md belum punya entri untuk perubahan ini (dicek CI base repo)")
    return items, ks.diff_hash(repo, merge_base, files)


def already_reminded(repo, dhash):
    path = os.path.join(repo, REMINDED)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            if fh.read().strip() == dhash:
                return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(os.path.join(repo, ks.STATE_DIR, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("*\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dhash)
    return False


def main(event):
    if event.get("stop_hook_active"):
        return
    cwd = project_dir(event)
    if not supported(cwd, event):
        return
    try:
        repo = ks.git(cwd, "rev-parse", "--show-toplevel").strip()
        items, dhash = pending_docs(repo)
    except ks.StatusError:
        return
    if not items or already_reminded(repo, dhash):
        return
    emit({"decision": "block", "reason":
          "venturo-kinerja (doc-sync): diff ini mengubah permukaan API/skema tanpa dokumen pasangannya. "
          "Di kinerja, doc_sync bernilai 10% skor final dan 0 bila dokumen tertinggal.\n"
          + "\n".join("- " + i for i in items)
          + "\nPerbarui dokumennya sekarang, atau jelaskan ke engineer kenapa kontrak tidak berubah. "
            "Pengingat ini hanya muncul sekali untuk keadaan diff yang sama."})


if __name__ == "__main__":
    guarded(main)
