---
weight: 30
tier: 2
enabled: true
conditional: false
categories:
  - oversized-function
  - excessive-complexity
  - oversized-file
  - oversized-component
  - too-many-parameters
  - deep-nesting
  - duplicate-logic
  - magic-value
  - dead-code
  - formatting-violation
  - file-placement
  - logic-error
  - unhandled-error
  - null-unsafe
  - off-by-one
  - wrong-api-usage
  - race-condition
---
## Dimensi structural

Fokusnya: laporkan pelanggaran ambang struktur, kode mati, pelanggaran formatter, file yang salah tempat, dan bug/kesalahan logika, sebagai temuan berkategori structural berikut evidence path:line — hanya untuk kode yang disentuh diff ini, bukan seluruh file lama yang kebetulan ikut terbaca. JANGAN beri skor untuk dimensi ini; sistem menghitungnya dari temuanmu.

Ambang struktur kode (pelanggaran = temuan kategori structural):
- function_length: maks 50 — hitung semua baris dari signature sampai penutup badan fungsi, TERMASUK baris kosong dan komentar.
- function_complexity: maks 10 — hitung tiap percabangan (if/else if, switch/case, loop, ternary, &&/|| dalam kondisi) sebagai satu; independen dari panjang baris.
- file_length: maks 800 — semua baris file (import, komentar, baris kosong ikut), untuk file BUKAN komponen UI.
- ui_component_length: maks 300 — sejenis file_length tapi khusus file komponen UI (mis. .tsx/.jsx).
- parameter_count: maks 5 — parameter posisional pada signature; receiver/`this` tidak dihitung, satu objek destructuring dihitung satu.
- nesting_depth: maks 4 — kedalaman blok bersarang MULAI DARI BADAN FUNGSI (level 0), tiap if/for/switch/try di dalam blok lain menambah satu level.
- duplication: maks 0 — blok kode identik/nyaris identik yang muncul lebih dari sekali pada diff/file yang sama.
- magic_values: maks 0 — literal angka/string tanpa nama di logika inti; literal di test, config, atau pesan log/error TIDAK dihitung.

Panduan kategori:
- oversized-function: fungsi melebihi function_length. BUKAN fungsi rumit tapi pendek (itu excessive-complexity).
- excessive-complexity: fungsi melebihi function_complexity, terlepas dari panjangnya. BUKAN fungsi panjang beralur lurus (itu oversized-function).
- oversized-file: file BUKAN komponen UI melebihi file_length. BUKAN file komponen UI (itu oversized-component).
- oversized-component: file komponen UI melebihi ui_component_length.
- too-many-parameters: signature melebihi parameter_count. BUKAN soal nama parameternya (itu parameter-naming).
- deep-nesting: blok bersarang melebihi nesting_depth, semestinya pakai early return/guard clause.
- duplicate-logic: blok berulang melebihi ambang duplication, semestinya diekstrak jadi util bersama. BUKAN kode tak terpakai (itu dead-code).
- magic-value: literal tanpa nama di logika inti, semestinya jadi konstanta bernama. Literal tanggal/waktu pakai datetime-format.
- dead-code: import/variabel/fungsi tak terpakai dan kode yang dikomentari mati, yang ikut masuk diff ini.
- formatting-violation: pelanggaran format mekanis yang semestinya diselesaikan formatter standar (gofmt; prettier/eslint). BUKAN soal pemilihan nama (itu naming-convention).
- file-placement: file/folder menyalahi struktur proyek (komponen di luar folder fiturnya, handler nyampur di paket domain, test jauh dari kodenya). BUKAN file kepanjangan (itu oversized-file).
- logic-error: kondisi atau alur logika yang salah (operator kebalik, kondisi salah, cabang if/else tertukar) sehingga perilaku tidak sesuai maksud kode — bukan soal gaya/struktur, soal benar-salahnya logika.
- unhandled-error: error/exception yang mungkin terjadi (return error, promise reject, panic) tapi tidak ditangani di jalur yang disentuh diff ini.
- null-unsafe: akses properti/pemanggilan method pada nilai yang bisa null/undefined/nil tanpa pengecekan sebelumnya.
- off-by-one: kesalahan batas indeks/loop/range (< vs <=, mulai 0 vs 1) yang bikin elemen terlewat atau out-of-range.
- wrong-api-usage: memanggil API/fungsi/library dengan cara salah sesuai dokumentasi/kontraknya (urutan argumen salah, parameter wajib kosong, method deprecated yang perilakunya beda).
- race-condition: akses/mutasi state bersama dari jalur concurrent (goroutine/thread/async) tanpa sinkronisasi semestinya.