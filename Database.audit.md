# BERITA ACARA
## QUALITY AUDIT READY TO RELEASE

**Nomor:** Work Order  
**[Nama Software]**

---

| Prepared | Quality Control | Quality Control | Quality Control |
|----------|----------------|----------------|----------------|
| /     /2025 | /     /2025 | /     /2025 | /     /2025 |
| | | | |
| **Nama**<br>Project Support | **Nama**<br>Project Lead | **Nama**<br>QA Engineer | **Nama**<br>CTO |

---

## DATABASE - QUALITY AUDIT

| # | Audit Activity | Checklist |
|---|----------------|-----------|
| **Standarisasi Pembuatan Tabel** | **Standarisasi Pembuatan Tabel** | **Standarisasi Pembuatan Tabel** |
| 1 | Apakah setiap tabel sudah menggunakan nama yang jelas tanpa prefix `m_`, `t_`, atau `tbl_`?<br><br>**Why:** Prefix m_, t_, tbl_ membuat nama tabel lebih panjang dan kurang menambah nilai plus. Nama tabel yang bersih lebih mudah dibaca dan di-query. | |
| 2 | Apakah setiap tabel sudah menggunakan bahasa Inggris dengan ejaan yang benar?<br><br>**Why:** Bahasa Inggris adalah standar global, akan mengikuti best practice dan memudahkan kolaborasi dengan tim internal maupun eksternal. | |
| 3 | Apakah setiap tabel sudah menggunakan bentuk plural (contoh: `users`, `orders`)?<br><br>**Why:** Memudahkan pemahaman struktur karena konsistensi plural menunjukkan tabel berisi *kumpulan entitas*, bukan satu entitas tunggal. | |
| 4 | Apakah setiap tabel sudah menggunakan format `snake_case` (contoh: `transaction_items`, `client_outlets`)?<br><br>**Why:** Format ini paling banyak digunakan di SQL dan memudahkan pembacaan nama tabel. | |
| 5 | Apakah setiap tabel memiliki kolom `id` dengan tipe VARCHAR(40) untuk menyimpan UUID (bukan auto increment)?<br><br>**Why:** UUID menghindari bentrok ID pada skenario replikasi atau migrasi data, dan lebih aman untuk expose di API karena tidak mudah ditebak. | |
| 7 | Apakah setiap tabel sudah memiliki kolom standar audit trail (`created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by`, `deleted_by`)?<br><br>**Why:** Kolom ini penting untuk melacak perubahan data dan memudahkan debugging. | |
| 8 | Apakah UUID dan audit_trail timestamp (`id`, `created_at`, `updated_at`, `deleted_at`) sudah di generate pada layer service / aplikasi, bukan menggunakan function database?<br><br>**Why:** Generate UUID di layer aplikasi memudahkan reuse UUID tersebut pada tabel child. Generate value timestamp layer aplikasi menjaga konsistensi timezone (bisa terjadi case timezone server aplikasi berbeda dengan timezone database) | |
| **Standarisasi Pembuatan Kolom** | **Standarisasi Pembuatan Kolom** | **Standarisasi Pembuatan Kolom** |
| 1 | Apakah nama kolom sudah menggunakan bahasa Inggris dengan ejaan yang benar?<br><br>**Why:** Bahasa Inggris adalah standar global, akan mengikuti best practice dan memudahkan kolaborasi dengan tim internal maupun eksternal. | |
| 2 | Apakah nama kolom sudah menggunakan format `snake_case` (contoh: `first_name`, `order_total`)?<br><br>**Why:** Format ini paling banyak digunakan di SQL dan memudahkan pembacaan nama kolom. | |
| 3 | Apakah kolom relasi sudah menggunakan format `{referenced_table_singular}_id` (contoh: `user_id`, `product_id`)?<br><br>**Why:** Memudahkan pemahaman relasi antar tabel. Menjelaskan jika relasi hanya ke 1 data (singular) | |
| 4 | Apakah semua kolom mandatory sudah didefinisikan sebagai `NOT NULL`?<br><br>**Why:** Memastikan integritas data dan mengurangi potensi bug. | |
| 5 | Apakah semua kolom opsional sudah didefinisikan sebagai `NULLABLE`?<br><br>**Why:** Memastikan kolom yang boleh kosong memang diizinkan untuk menyimpan nilai NULL. dan menghindari kebingungan antara kolom yang tidak diisi (NULL) dan kolom yang diisi dengan nilai default (misal: string kosong atau 0). | |
| 6 | Apakah setiap kolom yang memerlukan nilai default sudah memiliki default value (`CURRENT_TIMESTAMP`, `TINYINT default 0`, dll.)?<br><br>**Why:** Memastikan data tetap konsisten walaupun aplikasi tidak mengirim nilai eksplisit. | |
| 7 | Apakah kolom boolean sudah menggunakan prefix `is_`, `has_`, atau `can_` dan tipe data TINYINT(1) (contoh: `is_active`, `has_paid`)?<br><br>**Why:** Prefix ini memudahkan pemahaman bahwa kolom tersebut menyimpan nilai boolean (1 = true / 0 = false). | |
| 8 | Apakah kolom yang menyimpan mata uang sudah menggunakan tipe data `DECIMAL(18,2)`?<br><br>**Why:** Tipe data ini menghindari masalah pembulatan yang umum terjadi pada tipe data float. | |
| 9 | Apakah sudah berkomunikasi dengan tim produk untuk menentukan length kolom teks (`VARCHAR`) yang sesuai dengan kebutuhan bisnis?<br><br>**Why:** Panjang kolom yang terlalu pendek dapat menyebabkan data terpotong, sedangkan terlalu panjang dapat memboroskan ruang penyimpanan. | |
| 10 | Apakah kolom yang menyimpan teks panjang lebih dari 255 karakter sudah menggunakan tipe data `TEXT`?<br><br>**Why:** Tipe data `VARCHAR(255)` hanya cocok untuk teks pendek, sedangkan `TEXT` lebih fleksibel untuk teks panjang. | |
| 11 | Apakah kolom yang menyimpan teks panjang kurang dari 255 karakter sudah menggunakan tipe data `VARCHAR`?<br><br>**Why:** Gunakan `VARCHAR` untuk efisiensi penyimpanan dan performa. | |
| 12 | Apakah kolom dengan tipe data `ENUM` sudah dipastikan pilihan value nya tidak akan berubah? Jangan gunakan `ENUM` jika ada kemungkinan perubahan nilai.<br><br>**Why:** Perubahan nilai `ENUM` memerlukan migrasi database (ALTER TABLE), Dapat menjadi issue jika populasi data sudah besar. | |
| 13 | Apakah sudah menyimpan UTC pada semua kolom timestamp (`created_at`, `updated_at`, dll.)?<br><br>**Why:** Menyimpan dalam UTC menghindari kebingungan zona waktu dan memudahkan konversi ke zona waktu lokal di aplikasi. | |
| **Relasi & Index** | **Relasi & Index** | **Relasi & Index** |
| 1 | Apakah sudah menghindari foreign key constraint pada kolom relasi?<br><br>**Why:** Foreign key constraint dapat memperlambat operasi `INSERT`, `UPDATE`, dan `DELETE` pada tabel dengan populasi data yang besar, dapat menyebabkan deadlock jika tidak dikelola dengan baik, dan dapat membatasi fleksibilitas dalam perubahan skema database. | |
| 2 | Apakah kolom relasi sudah memiliki index untuk optimasi join?<br><br>**Why:** Index pada kolom relasi mempercepat operasi join yang sering dilakukan. | |
| 3 | Apakah kolom yang sering dijadikan filter di-query sudah memiliki index?<br><br>**Why:** Index pada kolom yang sering di filter mempercepat waktu respon query. | |
| 4 | Apakah kolom sudah menambahkan index pada kolom `deleted_at` untuk optimasi query soft delete?<br><br>**Why:** Mempercepat query yang sering memfilter data aktif / non-deleted. | |
| 5 | Apakah nama index sudah konsisten (contoh: `idx_users_email`, `idx_order_user_id`)?<br><br>**Why:** Konsistensi nama index memudahkan identifikasi fungsi index tersebut. | |
| 6 | Apakah sudah mengimplementasikan penggunaan unique index untuk kolom yang harus unik (contoh: `email` pada tabel `users`)?<br><br>**Why:** Unique index memastikan integritas data dan mencegah duplikasi. | |
| 7 | (Opsional) Apakah sudah menambahkan composite index untuk query multi kolom yang sering digunakan (contoh: `idx_order_user_id_status` Untuk `order_status` dan `payment_status`)?<br><br>**Why:** Composite index mengoptimalkan query yang melibatkan beberapa kolom sekaligus. | |
| **Performance** | **Performance** | **Performance** |
| 1 | Apakah query kritis (query kompleks / banyak join / sering digunakan) sudah diuji dengan `EXPLAIN ANALYZE` untuk memastikan performa?<br><br>**Why:** Memastikan query berjalan efisien dan mendeteksi scan all pada tabel dengan populasi data yang besar. | |
| 2 | Apakah sudah menghindari query `SELECT *` dan memilih kolom secara eksplisit?<br><br>**Why:** Meminimalkan data yang diambil dari database untuk menghemat memory, mempercepat query, dan mencegah data sensitif ikut terbawa. | |
| **Keamanan** | **Keamanan** | **Keamanan** |
| 1 | Apakah data sensitif seperti password disimpan dalam bentuk hash (`bcrypt`, dll.)?<br><br>**Why:** Melindungi akun pengguna jika terjadi kebocoran database. | |
| **Dokumentasi** | **Dokumentasi** | **Dokumentasi** |
| 1 | Apakah setiap tabel dan kolom sudah memiliki deskripsi/komentar di schema?<br><br>**Why:** Deskripsi membantu tim yang lain untuk memahami tujuan tabel dan kolom. | |
| 2 | Apakah sudah membuat ERD yang sesuai dengan implementasi database? Tutorial membuat ERD bisa dibaca di https://venturo-id.notion.site/Standarisasi-Doc-ERD-277aed79abbd8055a861f74065ad4525?pvs=74<br><br>**Why:** ERD membantu visualisasi struktur database dan relasi antar tabel. | |
