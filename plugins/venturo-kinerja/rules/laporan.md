# Format Laporan Review

Skill ini hanya mengatur bentuk laporan akhir. Validasi bukti, scope review,
severity, lifecycle issue, dan penentuan temuan yang dihitung verdict
diatur oleh skill `workflow`.

## Format Temuan

Untuk tiap temuan:

```text
### [Severity] Judul singkat
**File:** `path/file.go:42`

**Snippets:**
Block Code code yg bermasalah. 

**Situasi saat ini:**
Root cause dan jalur pemicu singkat.

**Dampak:**
Dampak konkret.

**Perbaikan:**
Arah perbaikan yang actionable.

**Issue:** [#N](url-issue)

Confidence: XX%
```

Baris `**Issue:**` wajib ada pada temuan yang sudah memiliki issue: gunakan
nomor dan URL persis yang dikembalikan tool issue sesuai lifecycle di skill
`workflow`. URL-nya mengarah ke halaman Issues aplikasi ini, bukan github.com.
Jika mode review tidak menyediakan tool issue atau temuan tidak dibuatkan issue,
hilangkan baris ini — jangan mengarang nomor issue.

Isi **Situasi saat ini** dengan root cause dan jalur pemicu yang ringkas, bukan
hanya gejala. Isi **Dampak** dan **Perbaikan** secara konkret dan actionable.

Jika ada lebih dari satu temuan, letakkan satu baris `---` di antara setiap
temuan. Jangan memakai pemisah setelah temuan terakhir atau setelah verdict.

Jangan duplikasi snippet kode dalam body jika sudah ada pada inline comment.
Isi confidence per temuan secara jujur berdasarkan kekuatan bukti, bukan untuk
sekadar melewati threshold.

## Metrik Akhir Wajib

Untuk review PR/diff, akhiri laporan dengan dua baris metrik final dalam urutan
ini:

```text
🧮 Review Confidence: XX%
Verdict: Approve
```

**Jangan menulis baris `📊 Score:`.** Skor dihitung backend dari daftar temuan
(mulai 100, dikurangi per temuan: Critical -15, High -10, Medium -5, Low -2,
Info 0, minimum 0) dan hanya disajikan lewat JSON aplikasi, bukan di body
laporan. Konsekuensinya: yang menentukan skor adalah severity yang kamu berikan
pada tiap temuan, jadi severity harus akurat. Baris `Verdict:` juga ditimpa
backend dengan cara yang sama.

`Review Confidence` adalah rata-rata confidence dari temuan aktif yang lolos
workflow dalam rentang 0-100. Jika tidak ada temuan aktif, isi angka confidence
berdasarkan keyakinan reviewer bahwa diff tidak memperkenalkan bug material.
Jangan memakai `N/A` pada review PR/diff.

Label `🧮 Review Confidence:` adalah kontrak parser backend. Jangan diganti
menjadi `Confidence`, `Quality Score`, `Architecture Accuracy`, atau variasi
lain.

Pada full source scan, manual review tanpa diff, atau branch review tanpa PR,
lewati baris metrik ini dan tetap tutup dengan satu verdict persis yang
dihitung dari temuan aktif yang lolos workflow:

- tanpa temuan pada level {{SEVERITY_SCOPE}}: `Verdict: Approve`
{{VERDICT_MEDIUM_RULE}}
- ada High: `Verdict: Needs work`
- ada Critical: `Verdict: Request changes`