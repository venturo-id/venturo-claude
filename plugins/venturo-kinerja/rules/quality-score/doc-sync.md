---
weight: 10
tier: 1
enabled: true
conditional: true
categories:
  - doc-existing
  - contract-sync-mismatch
  - incomplete-api-doc
  - stale-doc-timestamp
---
## Dimensi doc_sync

Tentukan apakah diff menyentuh permukaan API/kontrak (endpoint, schema, signature publik). Kalau ya, cek apakah dokumentasi terkait (README, komentar API, changelog) ikut diperbarui pada PR yang sama; kalau tidak, setor temuan kategori doc_sync berikut evidence path:line sebagai bukti. Skornya tetap dari dua boolean doc_sync_applicable/doc_sync_updated — temuan hanyalah bukti yang bisa dibantah developer.

Panduan kategori (evidence WAJIB path:line KODE yang berubah di diff, bukan path dokumennya — dokumen yang tertinggal tidak ada di diff, menunjuknya membuat temuan dibuang sistem):
- undocumented-api-change: diff mengubah kontrak tapi dokumen kontraknya tidak ikut diperbarui di PR yang sama.
- stale-api-doc: dokumen kontrak yang SUDAH ADA kini bertentangan dengan kode sesudah diff — bukan sekadar belum ditambah. Sebut dokumen yang bertentangan di note.
- missing-changelog-entry: perubahan kontrak terlihat pengguna API tanpa entri changelog di PR yang sama, padahal repo memeliharanya. Kalau repo tidak punya changelog, jangan laporkan.
- incomplete-api-doc: dokumen kontraknya ada dan tidak bertentangan, tapi tidak lengkap (parameter, kode error, syarat auth tidak dijelaskan). Sebut bagian yang kurang di note.
- contract-sync-mismatch: satu kontrak dideskripsikan di lebih dari satu tempat dan diff hanya memperbarui sebagian sehingga nama field/tipe/opsionalitas kini berbeda. Sebut sisi yang tertinggal di note.
- stale-doc-timestamp: dokumen kontrak punya penanda terakhir-diperbarui tapi penandanya tidak dinaikkan padahal isinya berubah di PR ini. Kalau dokumennya tidak punya penanda, jangan laporkan.