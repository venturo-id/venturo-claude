---
weight: 30
tier: 3
enabled: true
conditional: false
categories:
  - naming-convention
  - parameter-naming
  - datetime-format
---
## Dimensi readability

Fokusnya: laporkan pelanggaran standar penulisan pada diff ini — penamaan yang menyalahi konvensi bahasa/repo, nama parameter tidak deskriptif, format tanggal/waktu tidak standar — sebagai temuan berkategori readability berikut evidence path:line. Jangan melaporkan cacat logika atau ukuran kode di sini. JANGAN beri skor untuk dimensi ini; sistem menghitungnya dari temuanmu.

Panduan kategori:
- naming-convention: nama variabel/fungsi/tipe/konstanta/file menyalahi konvensi bahasa & repo (camelCase variabel/fungsi TS, PascalCase komponen React & exported Go, UPPER_SNAKE_CASE konstanta, prefix is/has/should untuk boolean). BUKAN nama parameter (itu parameter-naming) dan BUKAN letak file (itu file-placement).
- parameter-naming: nama parameter tidak deskriptif/menyesatkan: singkatan tak jelas (d, tmp, val2), nama tak cocok nilainya, boolean flag posisional yang tak terbaca maksudnya. BUKAN soal JUMLAH parameter (itu too-many-parameters).
- datetime-format: penanganan tanggal/waktu tidak standar: layout dirakit manual, waktu tanpa timezone eksplisit, format berbeda antar-endpoint untuk nilai sama. Patokan: nilai tanggal-waktu pada permukaan API memakai RFC3339/ISO-8601 UTC. BUKAN literal umum tanpa nama (itu magic-value).
- stale-comment: komentar (termasuk doc comment) yang tak lagi cocok dengan kode sesudah diff ini. BUKAN kode dimatikan dalam komentar (itu dead-code) dan BUKAN dokumen di luar kode (itu stale-api-doc).
- inconsistent-terminology: satu konsep domain disebut beberapa istilah berbeda di diff yang sama pada nama simbol, teks UI, atau field API. BUKAN pelanggaran bentuk penulisan (itu naming-convention).
- unclear-message: pesan error/log yang tidak bisa dipakai bertindak: teks generik, tanpa konteks operasi yang gagal, atau error dibungkus ulang sampai penyebab asli hilang.
- missing-doc-comment: simbol publik baru/berubah di diff ini tanpa doc comment padahal perilakunya tak jelas dari signature. BUKAN doc comment kedaluwarsa (itu stale-comment).