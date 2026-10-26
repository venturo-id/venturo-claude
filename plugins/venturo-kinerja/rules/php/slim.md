# Review Slim

Dipakai bila diff menyentuh route, middleware, container, atau handler Slim. Aturan PHP umum ada di skill induk `php`; di sini hanya yang khas Slim.

## Routing dan Middleware

- Urutan middleware menentukan perilaku. Middleware auth harus berjalan sebelum handler yang dilindungi; periksa route group dan penempatan `add()`.
- Route baru pada group yang dilindungi tidak otomatis aman bila handler membaca parameter kepemilikan dari input.
- Middleware yang tidak mengembalikan hasil `$handler->handle($request)` memutus rantai.

## Kontrak PSR-7

- Request dan Response bersifat immutable: hasil `withHeader`, `withStatus`, `withBody` wajib dipakai, bukan dibuang.
- Body stream hanya dapat dibaca sekali; periksa pembacaan ganda `getBody()->getContents()`.
- `getParsedBody()` dapat bernilai `null` bila content-type tidak cocok. Periksa penanganannya.

## Container dan Dependency

- Dependency diambil dari container, bukan dibuat langsung di handler, bila pola repo memang begitu.
- Service yang menyimpan state antar request pada container diperiksa dampaknya.

## Error Handling

- Error handler produksi tidak boleh menampilkan detail exception atau stack trace ke klien.
- Exception yang tidak tertangkap pada handler baru: pastikan ada penanganan yang menghasilkan status yang benar.
