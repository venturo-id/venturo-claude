---
per_finding: 10
---
--- ATURAN PENILAIAN QUALITY SCORE ---
Selain review biasa, nilai kualitas kode diff ini mengikuti aturan berikut.

Setiap temuan yang diterima memotong skor dimensinya sebesar nilai per_finding, berapa pun ukuran PR; skor dimensi berhenti di 0. Tidak ada klasifikasi severity yang mempengaruhi angka: satu temuan = satu potongan. Seluruh skor dihitung sistem dari temuan — JANGAN menyetor angka skor apa pun.