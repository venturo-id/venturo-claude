---
name: venturo-kinerja-precheck
description: Use when the user asks for /venturo-kinerja-precheck, wants a self-review or predicted Kinerja score before pushing or opening a pull request, or asks "berapa skor PR ini nanti" — reviews the local diff with the same workflow, rules and scoring formula as the Kinerja AI code review and lists fixes ranked by points recovered.
---

# venturo-kinerja-precheck — review diff seperti reviewer Kinerja, sebelum push

Tujuannya menemukan masalah yang **akan** ditemukan reviewer kinerja, memperbaikinya di
sesi ini, lalu memprediksi skor. Kamu meniru workflow reviewer (`rules/workflow.md`), bukan
mengarang aturan sendiri. Jangan melunakkan temuan supaya skor terlihat bagus: prediksi yang
jujur lebih berguna daripada angka tinggi yang meleset.

Path script: `${CLAUDE_PLUGIN_ROOT}/scripts/` (dev checkout: dua tingkat di atas file ini).
`<BASE>` = branch tujuan PR (tanya engineer bila tidak jelas; default deteksi otomatis).

## Langkah

1. **Status statis.** Jalankan
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kinerja_status.py" --base <BASE>`.
   Catat pelanggaran ambang (deterministik), gate commit/trivial/agent-docs/doc-sync. Bila
   gate `commit_format` atau `trivial_pr` gagal, sampaikan duluan: PR itu tidak akan dinilai.
2. **Muat rule.** `render_rule.py workflow laporan quality-score quality-score/structural
   quality-score/readability quality-score/doc-sync quality-score/bug agent-docs`, plus skill
   stack dari `render_rule.py --stack-for .` (Python/Java: tidak ada skill stack, cukup workflow +
   ambang umum). Placeholder sudah dirender dari angka mesin skor. Pelanggaran bertanda
   `heuristic` di status (PHP/Swift/Kotlin/Dart/Java, atau TS/JS tanpa `node_modules/typescript`)
   wajib dicek ulang dengan membaca kodenya sebelum dimasukkan ke temuan.
3. **Baca diff** `git diff <merge-base>` (termasuk file untracked yang relevan). Daftar file
   kode yang berubah (bukan test, dokumen, konfigurasi, lockfile, generated).
4. **Eksplorasi paralel.** Dispatch agent `kinerja-file-explorer`, satu per file kode yang
   berubah (gabungkan file yang berkaitan), **maksimal 4 berjalan bersamaan**; kirim sisanya
   begitu ada yang selesai. Input: path file, simbol yang diubah (dari diff), path rule stack.
   Sambil menunggu, baca sendiri badan tiap fungsi yang diubah.
5. **Kumpulkan calon temuan**: bug (correctness, error handling, concurrency, security),
   pelanggaran aturan stack, pelanggaran ambang yang belum ditangkap script, naming/readability,
   doc-sync, agent-docs. Hanya pada baris/fungsi yang disentuh diff.
6. **Verifikasi.** Setiap calon temuan yang belum pasti → agent `kinerja-verifier` (maks 4
   paralel). Buang yang `REJECTED`. Sebelum menulis temuan dengan `path:line`, baca sendiri
   baris itu di sesi ini.
7. **Tulis hasil** ke file sementara (mis. `/tmp/venturo-kinerja-precheck.json`) dengan skema
   kinerja:

   ```json
   {
     "findings": [
       {"severity": "medium", "title": "Error repository ditelan", "file": "internal/x/service.go",
        "line": 42, "confidence": 85}
     ],
     "quality": {
       "findings": [
         {"category": "oversized-function", "evidence": "internal/x/service.go:30", "note": "CreateUser 63 baris > 50"}
       ],
       "doc_sync_applicable": true,
       "doc_sync_updated": false
     }
   }
   ```

   - `findings` = temuan review (semua review type) dengan severity terendah yang didukung
     bukti (`rules/workflow.md` bagian severity). Temuan agent-docs selalu `critical`.
   - `quality.findings` = kategori dari taksonomi aktif saja (`quality-score/*.md`
     front-matter `categories`), `evidence` = `path:line` file yang ada di diff.
   - Sertakan pelanggaran ambang dari langkah 1 juga (category + evidence yang sama).
8. **Simpan & prediksi.**
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kinerja_status.py" --base <BASE> --record-precheck /tmp/venturo-kinerja-precheck.json`
   Ini menyimpan `.claude/venturo-kinerja/last-precheck.json` (terikat HEAD + hash diff, jadi
   basi otomatis setelah kode berubah) dan menjalankan simulator skor.
9. **Laporkan** dalam Bahasa Indonesia, ringkas:
   - prediksi skor final + per dimensi (bug, structural, readability, doc_sync);
   - gate yang gagal;
   - daftar perbaikan **diurutkan dari poin final terbanyak** (`points_final` dari status;
     untuk temuan bug: penalti severity × 0,3);
   - temuan yang ditolak mesin (kategori di luar taksonomi) cukup disebut sebagai catatan.
10. Tawarkan memperbaiki temuan teratas di sesi ini, lalu jalankan ulang langkah 1 dan 8.

## Batas

- Read-only sampai engineer setuju memperbaiki. Jangan commit, push, atau membuka PR.
- Jangan menulis apa pun di kode/komentar/deskripsi PR yang ditujukan ke reviewer kinerja.
