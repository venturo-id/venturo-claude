# Review PHP Berbasis Bukti

Nilai perubahan yang benar-benar dieksekusi, bukan preferensi gaya. Mulai dari diff, lalu telusuri caller, route, model, query, dan template yang diperlukan untuk membuktikan atau membantah dampak. PHP dinamis: jangan menyimpulkan tipe atau nilai tanpa melihat pemanggilnya.

Repo ini memakai beberapa framework. Aturan di bawah berlaku untuk semua. Bila diff jelas menunjukkan framework tertentu, ambil sub skill-nya lewat `get_skill` sebelum menulis temuan framework-spesifik.

## Correctness dan Error

- Telusuri tipe nilai yang mengalir ke fungsi yang diubah. Laporkan null/`array` vs `object` mismatch hanya bila ada jalur pemanggil nyata.
- Exception yang ditangkap lalu diabaikan (`catch (\Throwable $e) {}`) adalah temuan bila menutupi kegagalan yang penting bagi pemanggil.
- Perbandingan longgar (`==`, `in_array` tanpa strict) jadi temuan hanya bila tipe input dapat berbeda pada jalur nyata.
- Periksa nilai balik yang tidak diperiksa: `json_decode`, `file_get_contents`, `preg_match` dapat mengembalikan `null`/`false`.

## Input dan Trust Boundary

- Setiap nilai dari request, header, cookie, file, atau API luar wajib divalidasi sebelum dipakai. Tunjukkan jalurnya, jangan berasumsi.
- Casting bukan validasi. `(int)` menahan tipe, bukan rentang atau kepemilikan data.
- Untuk data milik tenant/user, buktikan filter kepemilikan diterapkan pada semua jalur baca dan tulis terkait.

## Database

- Query wajib parameterized untuk nilai dinamis. Interpolasi string ke SQL adalah temuan security, bukan gaya.
- Nama tabel/kolom dinamis harus dari daftar putih.
- Operasi yang harus atomik perlu batas transaksi yang jelas; periksa rollback pada jalur error.
- Query di dalam loop adalah N+1 bila jumlah iterasi mengikuti data. Tunjukkan sumber iterasinya.

## Security

- Secret tidak boleh hardcode. Nilai sensitif berasal dari env/config, dan file config yang di-commit tidak boleh memuat kredensial asli.
- `eval`, `unserialize` atas input tak tepercaya, `extract`, `assert` dengan string, dan `system`/`exec`/`shell_exec` tanpa escaping adalah temuan High atau lebih bila input dapat dikendalikan.
- Path file dari input wajib dinormalisasi dan dibatasi ke direktori yang diizinkan (path traversal).
- Upload: validasi tipe berdasar isi, bukan ekstensi atau `$_FILES['type']`; simpan di luar webroot atau matikan eksekusi.
- Output ke HTML wajib di-escape kecuali terbukti sudah aman. Nilai ke atribut, URL, dan JavaScript butuh escaping berbeda.
- Redirect dan callback dari input butuh daftar putih tujuan.
- Perbandingan hash/token pakai `hash_equals`; password pakai `password_hash`/`password_verify`.

## Struktur dan Dependency

- Autoload PSR-4: namespace harus cocok dengan lokasi berkas.
- Perubahan `composer.json` diperiksa dampaknya: versi mayor baru, paket tidak terawat, atau `minimum-stability` longgar.
- Berkas besar atau fungsi panjang bukan temuan tanpa dampak nyata; jadikan catatan bila mempersulit jalur yang sedang diubah.

## Severity

- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.
- Critical hanya bila bukti menunjukkan kompromi luas, kehilangan data besar/tidak dapat dipulihkan, atau outage luas.
- High untuk security boundary yang dapat dieksploitasi, korupsi data, atau perilaku inti yang salah dengan dampak material.
- Pilih level terendah yang sepenuhnya didukung bukti.
