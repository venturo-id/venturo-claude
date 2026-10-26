# Review CLAUDE.md / AGENTS.md

File instruksi agent dimuat ke SETIAP sesi agent. Tiap baris yang gemuk,
basi, atau tidak relevan dibayar di semua sesi dan menurunkan kepatuhan agent.

## Kapan berlaku

Hanya bila diff menambah atau mengubah isi salah satu file ini (di folder mana
pun): `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`,
`.claude/AGENTS.md`, atau file yang di-import `@path` dari file tersebut.

- Tidak ada file itu di diff, file itu dihapus, atau hanya di-rename tanpa
  perubahan isi → skill ini selesai tanpa temuan.
- Full source scan dan manual review tanpa diff → skill ini tidak berlaku.
- Bila berlaku, nilai isi AKHIR file utuh, bukan hanya baris yang diubah.
  Aturan "hanya baris yang diubah" di skill workflow tidak berlaku di sini.
- Membaca file root dan import-nya untuk skill ini tidak dihitung dalam
  anggaran eksplorasi skill workflow. Bila sebuah file root tidak bisa dibaca,
  jangan laporkan "delegasi tidak ada".

## Severity

Semua temuan skill ini `critical`. Aturan ini mengalahkan aturan severity dan
larangan "style/preferensi" di skill workflow: isi file instruksi agent adalah
perilaku agent, bukan gaya penulisan. Tiap temuan tetap wajib punya bukti:
path, baris, dan kutipan isi atau jumlah barisnya.

Judul temuan TETAP per cek (angka dan detail masuk `body`, bukan judul), supaya
issue tidak dobel di push berikutnya:

- `[agent-docs] <path> melebihi 200 baris`
- `[agent-docs] <path> memuat isi tidak relevan`
- `[agent-docs] Delegasi sub agent tidak jelas`

Satu cek menghasilkan paling banyak satu temuan per file; daftar semua baris
bermasalah di `body` temuan itu. `file` = path file yang dinilai. Untuk
delegasi: file root yang ada di diff; bila hanya import yang berubah, file root
yang meng-import-nya; bila ada beberapa, `CLAUDE.md` dulu, lalu `AGENTS.md`.
Jangan isi `line`.

## Cek 1 — Ukuran

Hitung baris secara akurat (mis. `wc -l`, atau nomor baris terakhir hasil
baca file). Bila jumlah pasti tidak bisa didapat, laporkan hanya bila file
jelas jauh di atas batas.

- Satu file > 200 baris → critical. Sebut jumlah barisnya.
- File + semua `@import`-nya > 200 baris → critical. Import tetap dimuat saat
  sesi mulai, jadi memecah file tidak mengurangi konteks.

## Cek 2 — Isi padat dan relevan

Isi file hanya boleh yang dibutuhkan di sebagian besar sesi. Tiap pola di bawah
→ critical (sebut baris dan kutip isinya):

1. Bisa dibaca dari kode: struktur folder, daftar dependency, ringkasan
   arsitektur, daftar file/endpoint, isi `package.json`/`go.mod`.
2. Prosedur lebih dari 5 langkah yang hanya dipakai sesekali — harus dipindah
   ke skill.
3. Aturan yang hanya berlaku untuk satu folder atau jenis file, ditulis di file
   root — harus dipindah ke `.claude/rules/` dengan `paths:`, atau ke CLAUDE.md
   di folder itu.
4. Riwayat: changelog, kronologi insiden, catatan "dulu begini", info usang.
5. Nasihat umum yang tidak bisa dicek: "tulis kode bersih", "hati-hati",
   "ikuti best practice".
6. Duplikat: aturan yang sama tertulis dua kali, di file ini atau di file
   yang di-import.
7. Aturan yang saling bertentangan.

Yang BOLEH ada: perintah build/test, konvensi yang berbeda dari default tool,
jebakan (gotcha) beserta alasannya, larangan keras.

## Cek 3 — Delegasi sub agent

Hanya untuk file root repo: `CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`, atau
`.claude/AGENTS.md` di root (termasuk file yang di-import-nya). File di
subfolder dan `CLAUDE.local.md` tidak dinilai di cek ini. Cek ini hanya jalan
bila salah satu file root itu (atau import-nya) ada di diff; diff yang hanya
menyentuh file subfolder melewati cek ini.

Nilai GABUNGAN semua file root itu beserta import-nya, walau diff hanya
menyentuh salah satunya: cukup satu bagian delegasi di salah satu file.

File root wajib punya bagian delegasi sub agent. Untuk tiap jenis pekerjaan yang
didelegasikan, bagian itu menyebut:

1. pemicu konkret kapan delegasi dilakukan,
2. agent/role tujuan,
3. input yang dikirim (tugas, batas scope/file),
4. output yang harus dikembalikan (format, ringkas),
5. batas: read-only atau boleh edit, dan jumlah paralel maksimal.

Critical bila:
- bagian delegasi tidak ada;
- hanya kalimat umum seperti "pakai subagent bila perlu";
- salah satu dari lima poin di atas tidak ada;
- agent kustom dirujuk dengan path di repo ini, tapi file itu tidak ada.

Agent bawaan tool (mis. `Explore`, `Plan`, `general-purpose`) dan agent yang
didefinisikan di luar repo tidak perlu file di repo — jangan dijadikan temuan.g
