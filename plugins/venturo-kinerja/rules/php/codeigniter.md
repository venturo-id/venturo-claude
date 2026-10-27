# Review CodeIgniter

Dipakai bila diff menyentuh controller, model, view, atau config CodeIgniter. Aturan PHP umum ada di skill induk `php`; di sini hanya yang khas CodeIgniter.

## Input dan Validasi

- `$this->input->post/get`, `$this->request->getVar/getPost`, dan `$_POST` langsung wajib lewat validation rule sebelum dipakai pada jalur tulis.
- `XSS filter` bawaan bukan pengganti escaping saat output.
- CSRF: periksa konfigurasi aktif dan form/endpoint baru yang mengecualikannya.

## Query

- Query Builder aman untuk nilai yang di-bind. `$this->db->query()` dengan string gabungan wajib memakai binding.
- `where` dengan array dari input bisa membuka filter yang tidak diinginkan; periksa sumber datanya.
- Pemanggilan model di dalam loop pada controller adalah N+1.

## Struktur

- Controller harus tipis; logika berulang yang disalin antar controller dicatat bila menyebabkan perilaku tidak konsisten.
- Library/helper kustom yang menyimpan state global diperiksa dampaknya pada request lain.

## Session, Auth, dan Config

- Periksa regenerasi session setelah login dan penghapusan session saat logout.
- Data sensitif tidak disimpan di session tanpa alasan.
- Config yang di-commit tidak boleh memuat kredensial asli; `ENVIRONMENT` produksi tidak boleh menampilkan error detail.

## View

- Nilai dinamis di view wajib di-escape (`esc()` atau `html_escape`) kecuali terbukti aman.
