Semua komentar review, penjelasan, dan laporan wajib dalam Bahasa Indonesia. Nama kode, istilah teknis, dan kutipan error tetap apa adanya.

# Gaya Ringkas

- Langsung tulis masalah, bukti, dampak, dan tindakan perbaikan.
- Hapus basa-basi, pujian, kata pengisi, dan pengulangan.
- Gunakan kalimat pendek, tetapi pertahankan rantai sebab-akibat yang diperlukan untuk membuktikan bug.
- Jangan mengorbankan kejelasan pada risiko security, kehilangan data, concurrency, atau tindakan permanen.
- Jangan mengubah fakta agar kalimat lebih pendek. Jika bukti belum cukup, telusuri kode terkait atau lewati temuan.

Pola yang disarankan: `[masalah]. [bukti/alur pemicu]. [dampak]. [perbaikan].`

Contoh: `Map dibaca dan ditulis oleh handler paralel tanpa sinkronisasi. Request bersamaan dapat memicu data race dan fatal error concurrent map read and map write. Lindungi akses dengan mutex atau ubah ownership state.`
