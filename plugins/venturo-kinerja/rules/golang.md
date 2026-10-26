# Review Go Berbasis Bukti

Nilai perubahan yang benar-benar dieksekusi, bukan preferensi gaya. Mulai dari diff, lalu telusuri caller, callee, interface, schema, dan test yang diperlukan untuk membuktikan atau membantah dampak. Jangan menganggap sebuah pola salah tanpa melihat kontrak dan lifecycle-nya.

## Correctness dan Error

- Pastikan setiap jalur error penting ditangani, dibungkus dengan konteks bila berguna, dan tetap dapat diperiksa dengan `errors.Is` atau `errors.As` bila kontraknya memerlukan.
- Laporkan `panic`, nil dereference, double response, resource leak, atau hasil salah hanya jika ada jalur eksekusi nyata.
- `panic` boleh untuk invariant startup yang tidak dapat dipulihkan; jangan tandai otomatis sebagai bug.
- Error yang sengaja diabaikan harus terbukti aman dari konteks, bukan otomatis menjadi temuan.

## Concurrency

- Identifikasi ownership dan lifecycle goroutine, channel, timer, dan shared state.
- Laporkan data race bila sedikitnya dua akses dapat berjalan paralel, salah satunya menulis, dan tidak ada happens-before atau sinkronisasi yang melindungi akses tersebut.
- Periksa cancellation dan goroutine leak pada operasi yang dapat menunggu atau hidup melewati request. `context.Context` tidak wajib untuk goroutine yang jelas selesai secara lokal.
- Mutex, atomic, channel, dan immutable ownership boleh digabung bila perannya jelas. Nilai keselamatan implementasi, bukan pilihannya.
- Deadlock harus didukung urutan lock, channel lifecycle, atau wait cycle yang konkret.
- Gunakan `go test -race` untuk dynamic race detection dan `go vet` sebagai pemeriksaan terpisah. Jangan mengklaim perintah berhasil jika tidak dijalankan atau gagal karena environment.

## HTTP, Database, dan Security

- Validasi input di trust boundary sesuai kontrak. Pastikan handler berhenti setelah response terminal.
- Propagasikan request context ke operasi I/O dan beri timeout pada outbound call yang dapat menggantung.
- SQL wajib parameterized untuk nilai dinamis. Periksa transaction boundary pada operasi yang harus atomik.
- Untuk data tenant, buktikan filter ownership/tenant diterapkan pada semua jalur baca dan tulis terkait.
- Tutup rows/body/resource pada semua jalur yang memilikinya. `defer` bukan satu-satunya implementasi yang valid.

## API dan Desain

- Periksa kompatibilitas signature, serialization, migration, dan caller sebelum menyatakan breaking change.
- Interface, preallocation, `strings.Builder`, `sync.Pool`, folder depth, dan bentuk package adalah pilihan desain/performa; jangan jadikan temuan tanpa dampak terukur atau pelanggaran pola codebase yang menyebabkan bug.
- Untuk performa, tunjukkan hot path, pertumbuhan kompleksitas, alokasi, query N+1, atau input yang membuat regresi material.

## Severity

- Critical hanya bila bukti menunjukkan kompromi luas, kehilangan data besar/tidak dapat dipulihkan, atau outage luas.
- High untuk security boundary yang dapat dieksploitasi, data race, panic runtime, korupsi data, atau perilaku inti yang salah dengan dampak material.
- Data race atau panic komponen biasa bukan Critical tanpa bukti blast radius tersebut.
- Jangan memakai label aturan lama sebagai severity otomatis. Pilih level terendah yang sepenuhnya didukung bukti.
