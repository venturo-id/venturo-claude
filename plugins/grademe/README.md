# grademe — Vibe Coding Scoring Plugin

`grademe` adalah skill/plugin Claude Code yang menilai sesi vibe coding-mu dari **transcript sesi nyata** (bukan self-report) atas 7 dimensi rubrik terkunci, lalu (opsional) mengirim skornya ke leaderboard [Vibescore](https://vibescore.venturo.pro).

Cara kerja singkat: `scripts/digest.py` membaca transcript JSONL sesi aktif → memampatkannya jadi digest ringkas → `scripts/validate.py --score` menghitung **skor deterministik** dari counter di digest (tanpa LLM sama sekali) → sebuah grader subagent segar membaca digest yang sama untuk bagian KUALITATIF saja (`misses`, saran, analisis prompt; anti bias self-grading) → keduanya digabung, lalu `scripts/validate.py` memvalidasi hasil gabungan itu secara mekanis sebagai gerbang wajib → skor dipresentasikan, dan di-upload otomatis bila env var lengkap.

> **v0.7.2:** skor tidak lagi dihasilkan LLM. Counter yang identik selalu menghasilkan skor yang identik — syarat mutlak untuk kompetisi. Konsekuensinya: **skor v0.6.0 di leaderboard tidak sebanding** dengan skor v0.7.2, dan sesi lama tidak bisa di-regrade dari server (BE menyimpan payload, bukan transcript).

## Instalasi & Update

Install (sekali):
```
/plugin marketplace add venturo-id/venturo-claude
/plugin install grademe@venturo-tools
```

Update ke versi terbaru:
```
/plugin marketplace update venturo-tools
/plugin update grademe@venturo-tools
```
Cek versi terpasang: `/plugin list` (pastikan `grademe` di versi terbaru). Aktifkan tanpa restart: `/reload-plugins`.

Env var untuk upload skor (opsional — tanpa ini, grademe tetap jalan tapi hanya lokal):
- `VIBESCORE_API_URL` — mis. `https://vibescore-be.venturo.pro`
- `VIBESCORE_API_KEY` — generate sekali di https://vibescore.venturo.pro/participants/ (token hanya tampil sekali; hilang → tombol rotate di halaman yang sama)

Detail langkah-per-langkah (termasuk fallback dev-only tanpa marketplace, cara set env permanen di `~/.zshrc`/`~/.bashrc`) ada di **[INSTALL.md](INSTALL.md)**.

## Cara Pakai

```
/grademe                          # menilai sesi yang SEDANG berjalan (live)
/grademe --transcript <path>      # override eksplisit: nilai file lain (dev/QA/instruktur)
```

Yang terjadi: skill mendeteksi sesi aktif, preprocess transcript-nya, dispatch grader subagent segar, validasi mekanis, lalu presentasikan **skor + breakdown 7 dimensi + daftar `misses` + 1 saran konkret untuk sesi berikutnya**. Bila `VIBESCORE_API_URL`+`VIBESCORE_API_KEY` terpasang, skor otomatis ter-upload ke leaderboard (tanpa perlu flag apa pun).

## Rubrik Penilaian (total 100, v0.7.2)

| Dimensi | Bobot | Yang dinilai |
|---|---|---|
| Planning First | 15 | Plan gate di awal sesi (plan disetujui SEBELUM eksekusi), bukan reaktif di tengah jalan |
| Context Quality | 15 | Referensi konkret (file/doc/constraint) tersebar di banyak prompt, bukan cuma di prompt pembuka |
| Task Decomposition | 15 | Pekerjaan dipecah jadi sub-task terstruktur (TodoWrite/TaskCreate atau urutan eksplisit) |
| Delegasi & Tooling | 18 | Orkestrasi subagent/skill/MCP yang terpakai nyata (bukan ritual/decoy) |
| Verifikasi | 20 | Test/build/run dijalankan, hasil dibaca, kegagalan ditindaklanjuti — bukan diterima buta |
| Efisiensi Token | 12 | Prompt lean, tanpa paste berulang atau read berlebihan |
| Dokumentasi | 5 | Penulisan README/docs/decision-log sebagai bagian dari kerja |

Aturan kunci:
- **Evidence-based & deterministik (v0.7.2):** `digest.py` menghitung `evidence_metrics` (counter deterministik dari transcript: plan/context/todo/test/waste/doc + keluarga volume kerja), lalu `validate.py --score` mengubahnya jadi angka lewat band-target per dimensi. Tak ada judgment LLM di jalur skor. Tak ada cap struktural: `misses` boleh KOSONG, tak ada cap total 98, tak ada `score_caps` (85/89). Tabel band lengkap ada di §"Bagaimana skoring bekerja" pada `SKILL.md`.
- **Clamp aplikabilitas (rule 9, anti-ritual):** sesi tanpa `substantive_work` (mengubah file eksisting / tulis via Bash / edit oleh subagent), tanpa `deep_investigation` (≥12 dari read + mcp + `subagent_tool_calls//3` yang HANYA dihitung bila ada dispatch yang benar-benar dikonsumsi), dan tanpa `verified_greenfield` (file KODE baru + output test-runner nyata) di-clamp ke band Mid pada planning/decomposition/delegation/documentation, dan 13 pada verification. Ritual tanpa kerja tidak bisa menembus Mid.
- **N/A + imputasi:** dimensi yang memang tak bisa dinilai — `verification` (tak ada yang berubah), `documentation` (itu + tanpa doc write), `token_efficiency` (<12 tool call) — ditandai N/A dan diberi nilai imputasi pada laju sesi itu sendiri, jadi sesi riset read-only tidak dihukum atas test yang memang tak relevan. Ketujuh key `breakdown` tetap ada dan `total_score == sum(breakdown)` selalu benar. **Guard aktivitas minimum:** sesi yang `activity_signal`-nya 0 (nol tool call, nol read, nol edit, nol test, nol delegasi) tidak mendapat imputasi sama sekali — dimensi N/A-nya memakai LANTAI band (`BAND_FLOOR`), karena mengimputasi dari laju yang seluruhnya lantai berarti memproduksi poin dari ketiadaan bukti. `score_basis.na_basis` melaporkan `"floor"` atau `"imputed"`.
- **Verifikasi tanpa test-runner tetap dihitung, tapi lebih murah.** Kalau `test_commands == 0` namun ada probe BERTARGET yang tertaut ke sesuatu yang sesi ini ubah/nyalakan (`verification_probes_linked ≥ 1` — mis. `curl` ke endpoint yang baru diperbaiki, `lsof -i :PORT` setelah menyalakan layanan), verification naik dari lantai 6 ke band 10. Bukti test-runner tetap lebih mahal (13+): probe membuktikan "aku memeriksa keadaan yang kuubah", bukan "aku punya uji regresi yang bisa diulang".
- Sesi dari harness selain Claude Code (mis. format JSONL tak dikenal `digest.py`) **ditolak total** — tidak ada fallback penilaian manual. Sesi Claude Code yang sah tapi tanpa satu pun balasan assistant (dibuka lalu ditinggalkan) berhenti dengan pesan tersendiri (exit 3), bukan disalahartikan sebagai harness asing.
- **Batasan jujur:** fixture ritual murni (`pure-ritual.jsonl`) masih mencetak **75** — gate volume-kerja berambang keras sengaja belum dirilis; `artifact_dispersion` + `no_edits_anywhere` diemit tapi belum diskor; `decomposition` N/A masih ditunda. Daftar lengkap "yang perlu dioptimalkan berikutnya" (11 item, termasuk verifikasi layanan eksternal yang masih tak terlihat dan uji diskriminasi yang belum dijalankan) ada di `CHANGELOG.md` dan terlacak sebagai entri #24–#34 di `BACKLOG.md`.

## Submission JSON (kontrak dengan vibescore-api)

Sumber kebenaran = `openapi.yaml` di repo `vibescore-be`, schema `ScoreSubmission`. Bentuk v0.7.2 (breakdown tetap 7 int seperti versi-versi sebelumnya — field top-level non-scoring bertambah 4 lagi: `applicable_dimensions`, `na_dimensions`, `weights_applied`, `score_basis`, semuanya ADITIF dan diserap BE ke `raw_payload` tanpa perubahan skema):

```json
{
  "participant": "string",
  "session_id": "string",
  "session_date": "ISO8601",
  "total_score": 0,
  "breakdown": {
    "planning": 0, "context": 0, "decomposition": 0,
    "delegation": 0, "verification": 0, "token_efficiency": 0,
    "documentation": 0
  },
  "applicable_dimensions": ["planning", "context", "decomposition", "delegation"],
  "na_dimensions": {
    "verification": {"reason": "string", "imputed_points": 0, "basis": "imputed"}
  },
  "weights_applied": {
    "planning": 15, "context": 15, "decomposition": 15,
    "delegation": 18, "verification": 20, "token_efficiency": 12,
    "documentation": 5
  },
  "score_basis": {
    "earned_applicable": 0, "max_applicable": 0,
    "activity_signal": 0, "na_basis": "imputed"
  },
  "misses": ["[verification/test_commands=0] string", "string tanpa counter"],
  "misses_typed": [
    {"dimension": "verification", "counter": "test_commands", "observed": 0, "text": "string"},
    {"dimension": null, "counter": null, "observed": null, "text": "string tanpa counter"}
  ],
  "next_session_advice": "string",
  "session_name": "string",
  "compacted": false,
  "prompt_analysis": {
    "weak_patterns": ["string"],
    "example_rewrites": [{"original": "string", "better": "string"}]
  },
  "transcript_meta": {
    "line_count": 0, "byte_size": 0, "sha256_prefix": "string",
    "first_timestamp": "ISO8601", "last_timestamp": "ISO8601"
  },
  "usage_totals": {
    "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0
  },
  "type_counts": {"user": 0, "assistant": 0},
  "tool_usage": { "skills": [], "subagents": [], "dispatch_totals": {}, "mcp": {}, "plan_mode": {} },
  "signal_availability": { "cc_version": "string", "has_tool_use_result": true, "has_attribution": true },
  "first_user_prompt": "string",
  "work_evidence": {
    "duration_minutes": 0, "user_turns": 0, "assistant_turns": 0,
    "error_events": 0, "errors_followed_up": 0, "plan_revisions": 0,
    "friction_present": false
  },
  "user_prompts": [
    {"ts": "ISO8601", "text": "string (verbatim, dipotong per-prompt maks 4000 char, suffix \"…[truncated]\" bila kepotong)"}
  ],
  "evidence_metrics": {
    "plan_before_first_edit": true,
    "todo_full_lifecycle": false,
    "test_commands": 0,
    "suppressed_tests": 0,
    "duplicated_prompt_blocks": 0
  },
  "grademe_version": "0.7.2"
}
```
*(`evidence_metrics` di atas hanya contoh sebagian. Bentuk aslinya berisi **45 counter** — sumber kebenarannya adalah `_EM_KEYS` di `digest.py --selftest`, yang gagal kalau daftar ini dan kode berbeda. Isinya: 20 counter dasar plan/context/todo/test/waste/doc, 5 counter anti-gaming v0.7.1 (`test_commands_with_output`, `todo_distinct_items`, `todo_items_completed`, `consumed_dispatches`, `reads_of_edited_files`), dan 20 counter baru v0.7.2 — volume kerja `work_edits`, `files_created`, `code_files_created`, `files_modified`, `work_lines_changed`, `lines_on_existing_files`, `bash_write_ops`, `subagent_edits`, `subagent_lines_changed`, `subagent_tool_calls`; delegasi & batas edit `delegated_edit_files`, `first_edit_line`, `first_edit_line_any`, `no_edits_anywhere`; dokumentasi forensik `doc_writes_any_md`, `doc_writes_subagent`; plan gate `empty_plan_gates`; verifikasi non-test-runner `verification_probes`, `verification_probes_linked`; dispersi `artifact_dispersion`. `digest_schema_version` sesi v0.7.2 = **7**; `validate.py` menolak digest dengan skema < 4.)*

`misses` **selalu array string** — backend mendeklarasikan `Submission.misses` sebagai `[]string`, jadi array objek dijawab `400 {"error":"JSON tidak valid: json: cannot unmarshal object into Go struct field Submission.misses of type string"}`. Bentuk terstruktur `{dimension, counter, observed, text}` (diutamakan — `observed` diverifikasi ke digest) dikirim di field aditif top-level `misses_typed`, yang otomatis mendarat di `raw_payload` BE; `misses` adalah render string dari item-item itu (`validate.py --render-misses`, format `[dimension/counter=observed] text`), sejajar item-per-item. String polos tanpa `misses_typed` tetap diterima (kompatibilitas mundur, satu versi ke depan). Field di bawah `misses`/`next_session_advice` opsional dari sisi server. `participant` diabaikan untuk identitas (server memakai `X-API-Key`). Array `events` dari digest **tidak pernah** dikirim — ia lokal saja (privasi + batas body 256KB); `user_prompts` (SEMUA prompt user genuine, verbatim urut, tiap prompt dipotong maks 4000 char, budget total 150k char) **memang dikirim** untuk audit originalitas leaderboard.

## Struktur File
- `.claude-plugin/plugin.json` — plugin manifest
- `skills/grademe/SKILL.md` — the skill (workflow, prompt grader kualitatif, dokumentasi band scoring, kontrak upload)
- `scripts/digest.py` — transcript preprocessor (JSONL → compact digest JSON, stdlib-only)
- `scripts/validate.py` — **produsen skor + gerbang mekanis**. Sebagai produsen: `--score --digest D.json` → tepat 6 key top-level `{breakdown, total_score, applicable_dimensions, na_dimensions, weights_applied, score_basis}` dari band-target (rule 8) + clamp aplikabilitas (rule 9) + imputasi N/A + guard aktivitas minimum (lantai band bila `activity_signal == 0`). Sebagai gerbang: breakdown arithmetic (7 int, sum == total_score), 10 field forensik verbatim vs digest (termasuk `user_prompts`+`evidence_metrics`), konsistensi bukti satu arah, bentuk kabel `misses` (WAJIB array string — `Submission.misses` di BE bertipe `[]string`) + pemeriksaan `misses_typed` (dimensi applicable, counter nyata, `observed` cocok dgn digest, panjang sejajar `misses`), cap 70 anti-hand-authored; TIDAK ADA `score_caps`/kuota `misses`; wajib exit 0 sebelum presentasi/upload. `--render-misses GRADER.json` merender miss bertipe → `{misses, misses_typed}` siap tempel (satu-satunya implementasi format kabel). `--selftest` menjalankan suite internalnya
- `test-transcripts/` — sample sessions (bad/mid/good + fixture adversarial/edge-case) dipakai sebagai regression suite scoring

## Riwayat Versi

| Versi | Inti perubahan |
|---|---|
| v0.7.2 | Skoring deterministik penuh: `validate.py --score` jadi PRODUSEN skor (`breakdown`/`total_score`/`applicable_dimensions`/`na_dimensions`/`weights_applied`/`score_basis`), grader subagent hanya mengembalikan `{misses, next_session_advice, prompt_analysis}` (misses bertipe `{dimension, counter, observed, text}`, dikirim sebagai string render di `misses` + struktur di `misses_typed` — `Submission.misses` di BE bertipe `[]string`); rule 9 clamp aplikabilitas (anti-ritual) + N/A dengan imputasi untuk verification/documentation/token_efficiency, plus guard aktivitas minimum (`activity_signal == 0` → LANTAI band, bukan imputasi); band verifikasi 10 untuk probe tertaut (`verification_probes_linked`) saat `test_commands == 0`; telemetri subagent async ter-join lewat `<task-notification>` + sidecar `subagents/`; **20 counter baru** (`evidence_metrics` 25 → 45, work-path filtered), `digest_schema_version` → 7; `cache_ratio` keluar dari skor; artefak rencana tak lagi men-set edit pertama (dan edit subagent kini men-set-nya); gate rencana kosong (`empty_plan_gates`) dikeluarkan dari hitungan; compaction tak lagi menyaring counter apa pun; sesi tanpa balasan assistant → exit 3; payload +4 key aditif → `raw_payload`; **nol perubahan BE/FE**. Efek terukur (n=128): median 53 → 53,5 · p75 66,25 → 76 · max 93 → 97 · Spearman 0,938. **Skor v0.6.0 tidak sebanding dengan v0.7.2** |
| v0.7.1 | Pengetatan gate + band-target deterministik: `evidence_metrics` 20→25 counter (`test_commands_with_output`, `todo_distinct_items`, `todo_items_completed`, `consumed_dispatches`, `reads_of_edited_files`), gating test-command per-segmen, rule 3 diperketat (verification butuh output test-runner nyata; delegation butuh `consumed_dispatches`/`mcp_substantive`), rule 8 `_check_band_targets` = plafon per-dimensi deterministik dari counter |
| v0.7.0 | Evidence-based matrix scoring: `digest.py` emit `evidence_metrics` (20 counter deterministik); grader memetakan counter → band Low/Mid/High lewat MATRIX di `SKILL.md`; SEMUA hard gate v0.6.0 dihapus (`score_caps` 85/89, kuota `misses` ≥2, cap total 98) — sesi mendapat apa pun yang counter-nya buktikan; `validate.py` menegakkan plafon satu arah (klaim band tinggi tanpa counter → tolak, skor lebih rendah selalu boleh); payload tambah `user_prompts` (semua prompt user verbatim, ber-budget, untuk audit originalitas) + `evidence_metrics`; `FORENSIC_FIELDS` jadi 10 field |
| v0.6.0 | Anti-gaming: bobot rubrik direbalance (15/15/15/18/20/12/5); `misses` wajib ≥2 → skor maks efektif 98; `score_caps` hard gate (sesi pendek → 85, tanpa friksi → 89); deteksi prompt sintetis dari `first_user_prompt`+`work_evidence`; `validate.py` jadi gerbang mekanis wajib; harness non-Claude-Code ditolak total |
| v0.5.0 | Dimensi `delegation` dinilai terukur (D1 subagent/D2 skill/D3 MCP) dari sinyal ground-truth (`toolUseResult`, `attributionSkill`) yang tak bisa dipalsukan peserta; sesi tanpa skill+subagent dibatasi ≤6/15 |
| v0.4.1 | Fix bug nyata: file sementara `/tmp` kini per-transkrip (`${TAG}` suffix), mencegah grading membaca digest/submission basi milik sesi lain |
| v0.4.0 | Payload upload diperluas: `prompt_analysis` kini benar-benar dikirim (sebelumnya bug ke-strip sebelum POST), plus `usage_totals`/`type_counts`/`grademe_version` |
| v0.3.0 | Grading sesi live jadi wajib (bukan opt-in); `digest.py` preprocessing (~10–160× lebih kecil dari JSONL mentah); endpoint pindah ke `venturo.pro` |
| v0.2 | `--upload` flag → POST JSON ke vibescore-api dengan API key peserta |
| v0.1 | Local scoring + JSON + narrative; install via marketplace `venturo-tools` |
