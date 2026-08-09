---
name: venturo-contract
description: Use when the user is wiring frontend to backend, asks for /venturo-contract, suspects the API contract and the implementation have drifted apart, or wants to know the real request/response shape of an endpoint before writing code against it.
---

# venturo-contract — kontrak dulu, tebakan belakangan

Bug integrasi FE–BE di Venturo hampir selalu berakar di satu hal: **satu pihak menebak
bentuk data pihak lain**. Skill ini menghentikan tebakan itu — bacakan kontraknya, dan
kalau kontrak dan kode sudah berbeda, katakan mana yang berbeda.

## Aturan yang mengikat

1. **Kontrak lebih dulu, selalu.** Cari dan baca dokumen kontraknya sebelum menyentuh
   file implementasi:
   `openapi.yaml` · `openapi.json` · `swagger.*` · `*.proto` · `schema.graphql` ·
   `docs/api/**` · koleksi Postman/Insomnia · `types/api.ts` yang di-generate.
2. **Kalau kontraknya tidak ada, katakan begitu.** Jangan diam-diam beralih membaca
   handler lalu menyajikan hasilnya seolah itu kontrak. Yang benar: "Repo ini tidak
   punya kontrak. Bentuk di bawah saya turunkan dari implementasi — bisa berubah tanpa
   pemberitahuan." Lalu tawarkan membuat kontraknya.
3. **Laporkan drift, jangan tambal.** Kalau kontrak bilang satu hal dan handler bilang
   hal lain, itu temuan — bukan hal untuk kamu perbaiki diam-diam. Sebutkan keduanya
   dan biarkan orangnya memutuskan mana yang benar.
4. **Jangan mengubah kode apa pun** dalam skill ini. Ini kerja baca.

## Bentuk keluaran

Satu kalimat ringkasan, lalu:

**Endpoint**

| Method | Path | Auth | Sumber |
|---|---|---|---|
| POST | `/api/v1/sessions` | Bearer | `openapi.yaml:142` |

**Bentuk data** — request dan response, field demi field, dengan tipe dan wajib/opsional.
Sebutkan nama field **persis** seperti di kontrak (`snake_case` vs `camelCase` adalah
sumber bug nyata, bukan detail kosmetik).

**Drift** — kalau ada:

```
DRIFT  field `total_score`
  kontrak      openapi.yaml:88   integer, wajib
  implementasi handler.go:214    float64, boleh null
  akibat       klien TS yang percaya kontrak akan pecah saat null masuk
```

**Catatan integrasi** — hal yang akan menggigit saat menulis klien: format tanggal,
bentuk error, aturan paginasi, field yang dijanjikan tapi tidak pernah diisi.

Tutup dengan **"Kontrak konsisten."** kalau memang tidak ada drift. Jangan tutup dengan
kalimat itu kalau kamu tidak benar-benar membandingkan keduanya.

## Untuk pekerjaan yang lebih dalam

Kalau yang dibutuhkan adalah pembacaan kontrak yang panjang di banyak file, delegasikan
ke subagent **`api-contract-reader`** (ikut dalam paket ini) — ia read-only dan konteks
sesi utamamu tetap bersih.
