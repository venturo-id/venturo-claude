# grademe — Vibe Coding Scoring Plugin

`grademe` adalah skill/plugin Claude Code yang menilai sesi vibe coding-mu dari **transcript sesi nyata** (bukan self-report) atas 7 dimensi rubrik terkunci, lalu (opsional) mengirim skornya ke leaderboard [Vibescore](https://vibescore.venturo.pro).

Cara kerja singkat: `scripts/digest.py` membaca transcript JSONL sesi aktif → memampatkannya jadi digest ringkas → sebuah grader subagent segar menilai HANYA dari digest itu (anti bias self-grading) → `scripts/validate.py` memvalidasi hasilnya secara mekanis (non-LLM) sebagai gerbang wajib → skor dipresentasikan, dan di-upload otomatis bila env var lengkap.

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

## Rubrik Penilaian (total 100, v0.6.0)

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
- `misses` **WAJIB ≥2 item** di setiap sesi → `total_score` efektif maksimum **98** (tak ada skor sempurna).
- `score_caps` (hard gate dari bukti kerja): sesi <15 menit atau <5 giliran user → cap **85**; sesi tanpa friksi tertangani (tak ada error/revisi plan yang ditangani) → cap **89**. Skor 90+ hanya lewat friksi nyata yang ditangani.
- Sesi dari harness selain Claude Code (mis. format JSONL tak dikenal `digest.py`) **ditolak total** — tidak ada fallback penilaian manual.

## Submission JSON (kontrak dengan vibescore-api)

Sumber kebenaran = `openapi.yaml` di repo `vibescore-be`, schema `ScoreSubmission`. Bentuk v0.6.0 (breakdown tetap 7 int seperti versi-versi sebelumnya — v0.6.0 hanya menambah field top-level non-scoring, semuanya diserap BE ke `raw_payload` tanpa perubahan skema):

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
  "misses": ["string"],
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
  "score_caps": { "cap": 100, "reasons": [] },
  "grademe_version": "0.6.0"
}
```

Field di bawah `misses`/`next_session_advice` opsional dari sisi server. `participant` diabaikan untuk identitas (server memakai `X-API-Key`). Array `events` dari digest **tidak pernah** dikirim (privasi + batas body).

## Struktur File
- `.claude-plugin/plugin.json` — plugin manifest
- `skills/grademe/SKILL.md` — the skill (rubric logic, output format)
- `scripts/digest.py` — transcript preprocessor (JSONL → compact digest JSON, stdlib-only)
- `scripts/validate.py` — mechanical validation gate: breakdown 7-int contract, `score_caps` enforcement, forensic verbatim check vs digest; wajib exit 0 sebelum presentasi/upload
- `test-transcripts/` — sample sessions (bad/mid/good + fixture adversarial/edge-case) dipakai sebagai regression suite scoring

## Riwayat Versi

| Versi | Inti perubahan |
|---|---|
| v0.6.0 | Anti-gaming: bobot rubrik direbalance (15/15/15/18/20/12/5); `misses` wajib ≥2 → skor maks efektif 98; `score_caps` hard gate (sesi pendek → 85, tanpa friksi → 89); deteksi prompt sintetis dari `first_user_prompt`+`work_evidence`; `validate.py` jadi gerbang mekanis wajib; harness non-Claude-Code ditolak total |
| v0.5.0 | Dimensi `delegation` dinilai terukur (D1 subagent/D2 skill/D3 MCP) dari sinyal ground-truth (`toolUseResult`, `attributionSkill`) yang tak bisa dipalsukan peserta; sesi tanpa skill+subagent dibatasi ≤6/15 |
| v0.4.1 | Fix bug nyata: file sementara `/tmp` kini per-transkrip (`${TAG}` suffix), mencegah grading membaca digest/submission basi milik sesi lain |
| v0.4.0 | Payload upload diperluas: `prompt_analysis` kini benar-benar dikirim (sebelumnya bug ke-strip sebelum POST), plus `usage_totals`/`type_counts`/`grademe_version` |
| v0.3.0 | Grading sesi live jadi wajib (bukan opt-in); `digest.py` preprocessing (~10–160× lebih kecil dari JSONL mentah); endpoint pindah ke `venturo.pro` |
| v0.2 | `--upload` flag → POST JSON ke vibescore-api dengan API key peserta |
| v0.1 | Local scoring + JSON + narrative; install via marketplace `venturo-tools` |
