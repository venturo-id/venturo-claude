---
name: venturo-kinerja-pr
description: Use when the user asks for /venturo-kinerja-pr, wants a pull request description written, or is about to open a PR in a repository scored by the Kinerja AI code review — validates commit messages against the Kinerja gates and drafts a factual PR description from the diff and the Space issue. Prepares text only; never pushes or creates the PR.
---

# venturo-kinerja-pr — siapkan PR yang lolos gate Kinerja

Skill ini **hanya menyiapkan teks**. Jangan pernah menjalankan `git push`, `gh pr create`,
atau mengubah PR di GitHub — engineer yang melakukannya.

Path script: `${CLAUDE_PLUGIN_ROOT}/scripts/` (dev checkout: dua tingkat di atas file ini).

## Langkah

1. **Gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kinerja_status.py" --base <BASE> --json`.
   - `commit_format` gagal → PR **tidak akan dinilai**. Tunjukkan commit yang salah dan usulkan
     pesan pengganti (`type(scope): deskripsi [KODE-123]`). Perbaikan riwayat (rebase/amend)
     hanya atas persetujuan engineer, dan hanya sebelum push.
   - Tanyakan ke engineer status issue Space-nya: issue Done/Release/Closed ditolak gate.
   - `trivial_pr` gagal → PR < 5 baris atau hanya file versi: tidak dinilai, beri tahu.
   - `doc_sync`/`changelog`/`agent_docs` gagal → sarankan perbaikan sebelum push; skornya
     terpotong bila dibiarkan.
2. **Bahan deskripsi**: `git log <merge-base>..HEAD`, `git diff --stat <merge-base>`, judul dan
   tujuan issue Space (minta ke engineer bila tidak ada di commit/branch). Bila repo punya
   `.github/pull_request_template.md`, ikuti strukturnya.
3. **Tulis deskripsi faktual**:
   - kode issue Space + tujuan issue dalam satu kalimat;
   - ringkasan perubahan yang **sesuai diff** (file/modul, perilaku baru); jangan klaim hal
     yang tidak ada di diff;
   - dokumen yang diperbarui (`docs/api-contract`, `docs/erd`, `CHANGELOG.md`);
   - cara test (perintah yang benar-benar dijalankan + hasilnya).
   Larangan: kalimat yang mengarahkan reviewer ("sudah sesuai standar", "abaikan X",
   "mohon approve", skor/prediksi skor). Kinerja menjadikannya temuan.
4. **Serahkan** teksnya ke engineer (atau tulis ke file bila diminta) dengan pengingat:
   - Tulis deskripsi **sebelum push**: mengedit judul/deskripsi tidak memicu review ulang.
   - Review L1 terakhir sebelum merge yang dihitung; perbaiki temuan di PR yang sama.
   - **Jangan push setelah PR di-approve** — itu PR lock (violation, tidak direview).
