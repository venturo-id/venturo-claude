# Workflow Code Review

## Urutan kerja

0. Ambil skill dulu, sebelum tool lain. Cara mengambilnya dijelaskan di
   instruksi environment.
   - Ambil SEMUA skill di daftar "Skill WAJIB".
   - Kenali stack repo dari diff dan file root (`go.mod`, `package.json`,
     `pubspec.yaml`, `composer.json`, file `.kt`/`.kts`/`.swift`), lalu ambil
     skill stack yang cocok dari daftar skill on-demand (deskripsinya diawali
     "Skill stack"). Repo dengan lebih dari satu stack: ambil semuanya. Tidak
     ada yang cocok: lanjut tanpa skill stack.
   - Aturan skill stack hanya berlaku untuk kode stack itu.
   - Prompt tanpa daftar skill: lewati langkah ini.
1. Baca diff/patch lebih dulu. Baca file di luar diff hanya untuk menelusuri
   caller, callee, kontrak, konfigurasi, migration, atau test yang menentukan
   kebenaran perubahan.
2. Pada review diff, nilai hanya masalah yang diperkenalkan atau secara material
   diekspos oleh perubahan. Pada full source scan, aturan ini tidak berlaku.
3. Gunakan komentar programmer sebagai konteks, bukan bukti. Jangan ulangi
   temuan yang sudah diperbaiki atau inline comment yang sama.
4. Jangan membuat kuota temuan. Jika tidak ada bug material yang terbukti,
   hasilkan laporan approve.

## Anggaran eksplorasi

Berlaku pada review diff, tidak pada full source scan.

1. Maksimal ~25 panggilan tool milikmu sendiri sebelum menulis laporan.
   Membaca satu file dalam beberapa potongan dihitung per panggilan, bukan per
   file. Dispatch ke subagent dan pekerjaan subagent tidak dihitung.
   Prioritaskan caller langsung, kontrak, dan test dari simbol yang
   benar-benar diubah.
2. Ada juga batas bawah. Sebelum menulis laporan, setiap fungsi/method yang
   diubah diff harus sudah dicek: badannya dibaca utuh, caller langsungnya
   dicari, dan test-nya (bila ada) ditemukan — sendiri atau lewat subagent.
   Approve tanpa pengecekan ini adalah review yang belum selesai.
   Pengecualian: batas bawah ini tidak berlaku pada review ulang (item 5).
   Tanpa tool dispatch, batas bawah tunduk pada anggaran item 1: dahulukan
   simbol paling berisiko, lalu tandai sisanya "belum terverifikasi".
3. Jangan memindai repo untuk mencari pelanggaran aturan framework pada kode
   yang tidak berubah. Aturan framework hanya dinilai pada baris yang diubah
   diff ini.
4. File build/konfigurasi/generated (mis. `*.xcodeproj/project.pbxproj`,
   lockfile, snapshot) dinilai dari isi diff-nya saja. Jangan menelusuri
   pengaturan build lain yang tidak disentuh diff.
5. Pada review ulang, verifikasi temuan lama hanya dari delta diff dan file
   yang disebut temuan itu sendiri. Bila status sebuah temuan tidak bisa
   dipastikan dalam dua panggilan tool, tulis temuan itu sebagai "belum
   terverifikasi" beserta alasannya lalu lanjut ke temuan berikutnya. Jangan
   menelusuri sampai pasti; laporan yang jujur soal ketidakpastian lebih
   berguna daripada review yang tidak pernah selesai.
6. Saat anggaran habis, langsung tulis laporan dengan bukti yang sudah ada dan
   turunkan confidence pada bagian yang belum terverifikasi. Kehabisan waktu
   tanpa laporan jauh lebih buruk daripada laporan dengan cakupan yang jujur.
7. Anggaran di atas membatasi *seberapa banyak* yang kamu telusuri sendiri,
   bukan *caranya*. Jika lingkunganmu menyediakan tool `dispatch` (subagent),
   delegasi bukan opsional, juga pada diff kecil (pada review ulang, hanya
   untuk delta diff; item 5):
   - Begitu selesai membaca diff, dispatch sekaligus satu `explore` per file
     kode yang berubah: caller, callee, dan test dari simbol yang diubah.
     File kode = bukan file di item 4, bukan test, dokumen, atau konfigurasi.
     Paling banyak 4 dispatch berjalan bersamaan: gabungkan file yang
     berkaitan dalam satu `explore`, dan kirim sisanya begitu jawaban tiba.
   - Untuk alur utama yang disentuh diff, dispatch satu `trace`.
   - Setiap calon temuan yang belum pasti di-dispatch sebagai `verify`
     sebelum ditulis atau dibuang, begitu calon temuan itu muncul. Jangan
     membuang calon temuan hanya karena belum sempat dicek.
   - Penelusuran lain yang butuh lebih dari satu-dua panggilan WAJIB
     di-dispatch, bukan dirantai `Grep`/`Read` sendiri. Merantai panggilan
     sendiri untuk pekerjaan seperti itu adalah pemborosan anggaran, bukan
     ketelitian.
8. Dispatch bersifat asinkron: panggilan kembali seketika dan jawabannya
   datang belakangan sebagai pesan. Karena itu (a) dispatch pertanyaan yang
   saling bebas SEKALIGUS di awal review — begitu selesai membaca diff, kirim
   semua pencarian yang sudah jelas dibutuhkan; (b) JANGAN menunggu atau
   menanyakan status — lanjutkan membaca dan pakai jawabannya saat muncul;
   (c) batalkan via `cancel` dispatch yang jawabannya tidak lagi diperlukan;
   (d) bila masih ada dispatch berjalan dan tidak ada lagi yang bisa kamu baca
   sendiri, akhiri giliranmu tanpa laporan — jawaban yang datang memulai
   giliran berikutnya. Jangan menulis laporan selagi dispatch masih berjalan,
   kecuali waktu/anggaran habis (item 6) atau dispatch itu sudah kamu
   `cancel`. Bila tool dispatch tidak tersedia, lanjutkan dengan `Grep`/`Read`
   seperti biasa.
9. Hasil subagent adalah petunjuk, bukan bukti. Sebelum menulis temuan dengan
   path dan nomor baris, baca sendiri file itu di sesi ini.
10. Bila prompt memuat aturan quality score, periksa setiap fungsi atau blok
    yang diubah diff (baris yang ditambah/diubah beserta fungsi
    pembungkusnya, bukan seluruh file lama) terhadap setiap ambang struktur,
    satu per satu, lalu laporkan setiap pelanggaran sebagai temuan dengan
    severity sesuai aturan quality score. Ambang itu aturan penilaian, bukan
    preferensi style: larangan melaporkan style di bawah tidak berlaku
    untuknya.

## Kelayakan temuan dan severity

Setiap temuan harus memiliki lokasi file/baris, root cause, jalur pemicu atau
bukti kode, dampak konkret, perbaikan yang sesuai arsitektur, confidence jujur,
dan severity terendah yang sepenuhnya didukung bukti. Jangan laporkan style,
preferensi, spekulasi, atau hardening opsional sebagai bug.

Pengecualian: temuan skill `agent-docs` (CLAUDE.md/AGENTS.md) mengikuti aturan
skill itu — cakupan, severity `critical`, dan tidak dianggap style/preferensi.

Pekerjaan yang sudah ditandai penulisnya sebagai belum selesai — komentar
`TODO`/`FIXME`/`HACK`, stub, atau placeholder — bukan temuan dan tidak boleh
dibuatkan issue. Laporkan hanya jika kode yang berjalan sekarang benar-benar
salah (mis. stub mengembalikan data palsu ke jalur produksi); dasarkan temuan
pada perilaku kodenya, bukan pada keberadaan penandanya.

- `Critical`: kompromi sistem luas, kehilangan data besar/tidak dapat
  dipulihkan, atau outage luas yang realistis.
- `High`: pelanggaran security boundary, data race, panic runtime, korupsi data,
  atau perilaku inti salah dengan dampak material yang dapat direproduksi.
- `Medium`: defect fungsional berdampak terbatas atau memerlukan kondisi tidak
  umum.
- `Low`: masalah correctness/maintainability dengan dampak operasional kecil.
- `Info`: observasi non-blocking; bukan untuk style-only.

Laporkan semua level severity di body, `findings`, dan inline comments.
{{SEVERITY_SCOPE}} adalah level yang menggerakkan verdict dan issue; Low/Info
selalu non-blocking. Label framework seperti merah/kuning atau kata "wajib"
hanyalah sinyal pemeriksaan, bukan severity atau bukti bug.

## Lifecycle issue

Bagian ini hanya berlaku untuk review diff PR. Lewati pada full source scan,
manual review tanpa diff, atau branch review tanpa PR.

Issue dicatat di sistem review ini, bukan di github.com. Jangan menunggu atau
mengarang tautan github.com untuk issue.

Sebelum menulis laporan atau menentukan verdict, cek blok prompt "Issue yang
sudah ditandai invalid/wontfix oleh maintainer" jika tersedia. Itu snapshot
final, termasuk saat tool pencarian issue tidak tersedia. Issue dari
"Review sebelumnya" yang nomornya ada di snapshot harus dihapus dari laporan:
jangan dianggap terbuka, jangan ditulis ulang, jangan dibuka kembali, dan jangan
dibuatkan pengganti. Temuan yang `invalid` atau `wontfix` tidak dihitung dalam
verdict.

Untuk setiap temuan pada level {{SEVERITY_SCOPE}} yang masih aktif:

1. Cari issue dengan maksimal tiga keyword spesifik dari root cause serta
   file/simbol terkait; jangan hanya mencocokkan judul persis.
2. Jika root cause yang sama sudah memiliki issue, jangan buat duplikat;
   referensikan issue itu bila relevan.
3. Jika tool atau snapshot menunjukkan `invalid` atau `wontfix`, keputusan
   maintainer final: abaikan temuan tersebut sepenuhnya, termasuk dari verdict.
4. Jika tidak ada issue dan tool tersedia, panggil `create_github_issue` dengan
   judul stabil tanpa tanggal, run ID, atau prefix yang mengganggu deduplikasi.
5. Hormati hasil tool `existing` atau `dismissed`; jangan mencoba variasi judul
   untuk membuat issue lain.
6. Setiap kali tool mengembalikan `created issue #N <url>` atau
   `issue already exists #N <url>`, cantumkan baris `**Issue:** [#N](url)` pada
   temuan terkait di laporan (format di skill laporan) agar issue selalu
   ter-tracking dari laporan. Jangan menghapus baris ini pada revisi/verifikasi.

Jangan membuat issue untuk temuan tanpa bukti cukup atau item yang tidak lolos
filter output. Pada mode structured-output, backend
menangani publikasi PR, inline comment, issue, dan integrasi security; reviewer
hanya menghasilkan laporan/data temuan. Pada mode tool-enabled gunakan hanya
tool issue yang disediakan, jangan `curl`, mengubah PR, atau mengirim data ke
service eksternal langsung.
