# Review Laravel

Dipakai bila diff menyentuh Eloquent, route, middleware, job, atau migration Laravel. Aturan PHP umum ada di skill induk `php`; di sini hanya yang khas Laravel.

## Eloquent dan Query

- Relasi yang diakses di dalam loop tanpa `with()`/`load()` adalah N+1. Tunjukkan loop dan relasinya.
- `Model::all()` atau query tanpa batas pada tabel yang tumbuh: periksa paginasi.
- `$fillable`/`$guarded`: `create`/`update` dengan `$request->all()` tanpa batas kolom adalah mass assignment. Periksa kolom sensitif (`role`, `is_admin`, `status`).
- `DB::raw` dengan nilai dari input wajib parameterized.
- Scope global dan soft delete: pastikan query yang diubah tidak melewati filter yang dibutuhkan.

## Request dan Validasi

- Input wajib lewat Form Request atau `$request->validate()`. Pemakaian langsung `$request->input()` tanpa validasi pada jalur tulis adalah temuan.
- Route model binding tidak menjamin otorisasi. Periksa Policy/Gate atau pengecekan kepemilikan.
- Middleware auth pada route group: pastikan route baru berada di dalam group yang tepat.

## Response dan Kebocoran Data

- API Resource / `toArray` yang mengirim seluruh model dapat membocorkan kolom sensitif.
- `dd`, `dump`, `var_dump`, dan log berisi data sensitif tidak boleh masuk jalur produksi.

## Job, Queue, dan Jadwal

- Job yang dapat diulang harus idempoten; periksa efek ganda pada pembayaran/notifikasi.
- Operasi lambat di dalam request seharusnya masuk queue bila polanya sudah ada di repo.

## Migration

- Perubahan destruktif (drop/rename kolom, ubah tipe) diperiksa terhadap kode yang masih memakainya dan terhadap data lama.
- Migration tanpa cara mundur yang aman perlu disebut.
