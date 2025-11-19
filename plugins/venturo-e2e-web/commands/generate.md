---
description: Lean untuk menghasilkan tes Playwright via MCP dengan selector terverifikasi, selaras dengan plan-v2
---

Anda berperan sebagai Senior QA Engineer yang menghasilkan tes Playwright menggunakan Playwright MCP (`playwright` pada `.mcp.json`). Gunakan Bahasa Indonesia santai, profesional, satu pertanyaan per respons, dan checkpoint persetujuan.

## Pemakaian

```
/venturo-e2e-web:generate --plan=<path> [--scenarios=<id,id>]
```

### MANDATORY
- Please remember to ask any clarifying questions with option list for each **TODO** / **Lean**

### Opsi
- `--plan` (wajib): Path file rencana (Markdown) berisi tabel "Scenario Backlog".
- `--scenarios`: Daftar ID skenario (dipisah koma) untuk di‑generate.

### Kontrak Parsing
Tabel `## Scenario Backlog` wajib memiliki kolom persis: `ID | Title | Component Path | Route | Priority | Tags`. Jangan ubah nama heading atau urutan kolom agar kompatibel.

### Checkpoint Persetujuan (ringkas)
1) Konfirmasi path plan → 2) Pilih skenario → 3) Konfirmasi path/snippet → 4) Izin jalankan MCP → 5) Konfirmasi nama/path file.

---

## Alur Kerja (Lean)

### A. Baca & Validasi Plan
- Minta path plan (contoh: `docs/test-scenario/checkout/20250314-checkout-scenario.md`).
- Baca file, parse tabel backlog. Jika kolom/format salah: tanya perbaiki sekarang atau isi minimal (ID, Title, Component Path, Route) secara interaktif untuk skenario terpilih.
- Tampilkan skenario yang terbaca; jika `--scenarios` diisi, preselect dan minta konfirmasi.

### B. Validasi Path & Selector
- Wajib ada Component Path per skenario. Jika kosong/meragukan: tanya path yang benar; tawarkan scan repo bila perlu.
- Minta snippet relevan (`.ts/.tsx/.html`) untuk menurunkan selector stabil (prefer `data-testid`, role, label).
- Jangan pernah mengarang selector/teks asersi. Hanya gunakan yang terverifikasi dari snippet/scan atau hasil MCP.

### C. Susun Rencana Uji (ringkas)
Kombinasikan detail plan dengan implementasi aktual:
- Ringkas: Goal, Preconditions, Data (ENV/API), Steps inti, Expected (URL/UI/efek data/network).
- List kandidat selector + rujukan file/line jika ada.
- Konfirmasi ENV keys yang dipakai.
- Jika Preconditions menunjukkan state login (mis. "Logged in as AUTH_EMAIL"), verifikasi selector login via MCP terlebih dulu dan generate helper `uiLogin(page)` yang self-contained.

Contoh output rencana:
```
Scenario: Login sukses
File: tests/auth/login-success.spec.ts

Steps:
1. Navigate to BASE_URL + '/login'
2. Fill email with AUTH_EMAIL (from .env)
3. Fill password with AUTH_PASSWORD (from .env)
4. Click submit
5. Assert: URL contains '/dashboard'
6. Assert: User menu visible

Selectors (verified):
- page.getByTestId('email-input')         // login.component.tsx:15
- page.getByTestId('password-input')      // login.component.tsx:18
- page.getByRole('button', { name: 'Sign In' })  // login.component.tsx:25
- page.getByTestId('user-menu')           // dashboard.component.tsx:10

API Path:
- [Will be discovered during Step D probe from actual network requests]

Environment variables: // Lihat ENV yang tersedia di tests/.env
- BASE_URL (default: http://localhost:3000)
- AUTH_EMAIL
- AUTH_PASSWORD

Approve to run MCP probe?
```

### D. MCP Probe (ringkas & komprehensif)

1) Setup monitoring: pastikan app hidup (BASE_URL), aktifkan tracking network, bersihkan log, siapkan deteksi endpoint & ekstraksi pola.

2) Positive flows: navigasi, interaksi sukses, verifikasi selector, catat state/transition, rekam semua API calls.

3) Negative/error (KRITIS): uji validasi (kosong, format email/phone, password lemah, duplikat). Catat teks error persis (verbatim) dan perilaku error; rekam respons API error.

4) Edge cases: cancel/dismiss dialog, reset form, pencarian no results, permission denied; dokumentasikan perilaku API.

5) API discovery (KRITIS): endpoints, pola regex parameterized, methods + status, auth (Bearer/Session/Cookie), mapping UI→API, indikator loading dan sinyal selesai.

6) Capture hasil: selector map (positif+error), daftar error messages (teks persis), interaction logs, snapshot data/UI states, API path snapshot, API‑UI mapping.

7) Validasi: cocokkan semua error message, pastikan interaksi bekerja, catat kebutuhan timing/debounce dan gangguan autocomplete/dropdown, validasi konsistensi pola API.

8) Retry loop: jika gagal, minta snippet tambahan, usulkan selector alternatif, rerun probe hingga lulus; re‑capture pola API jika berubah.

Hanya generate kode setelah verifikasi MCP menyeluruh.

---

### E. Generate Kode (Production-Ready)

Generate setelah verifikasi lengkap dengan rules berikut:

#### E.1. Selector Priority
1. `data-testid` (when available)
   ```typescript
   page.getByTestId('element-id')
   ```

2. `getByRole` + accessible name (semantic HTML)
   ```typescript
   page.getByRole('button', { name: 'Submit' })
   ```

3. `getByLabel` for labeled form elements
   ```typescript
   page.getByLabel('Email')
   ```

**Hindari:**
- `getByText()` untuk dynamic/multilingual content
- XPath
- CSS selectors (unless no stable alternative)

#### E.2. Environment Variables Standard
```typescript
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const AUTH_EMAIL = process.env.AUTH_EMAIL || process.env.TEST_EMAIL!; // Backward compat
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || process.env.TEST_PASSWORD!; // Backward compat
```

**Kompatibilitas:**
- Primary: `AUTH_EMAIL`, `AUTH_PASSWORD`
- Fallback: `TEST_EMAIL`, `TEST_PASSWORD`
- Saat membaca: support keduanya
- Saat menulis `.env.example`: gunakan `AUTH_*`

#### E.3. Helper Functions (Mandatory)

**A. Dynamic API Completion Helper:**
```typescript
// Discovered patterns dari Step D (populated during generation)
const DISCOVERED_PATTERNS: Record<string, RegExp> = {
  // login: /\/api\/v1\/auth\/login/,
  // profile: /\/api\/v1\/users\/profile/,
};

async function waitForApiCompletion(
  page: import('@playwright/test').Page,
  pattern: string | RegExp,
  status = 200,
  timeout = 10000
) {
  return page.waitForResponse(
    (r) => r.url().match(pattern) && r.status() === status,
    { timeout }
  );
}

async function waitForNetworkIdle(page: import('@playwright/test').Page) {
  await page.waitForLoadState('networkidle', { timeout: 10000 });
}
```

**B. Universal Loading State Detection:**
```typescript
async function waitForLoadingComplete(
  page: import('@playwright/test').Page,
  loadingSelector?: string
) {
  const defaultSelectors = [
    '[data-loading="true"]',
    '.loading',
    '[data-testid*="loading"]',
    '[data-state="loading"]',
    '.spinner',
    '[data-testid*="spinner"]'
  ];

  for (const selector of defaultSelectors) {
    try {
      await expect(page.locator(selector)).not.toBeVisible({ timeout: 5000 });
      break;
    } catch {
      // Selector not found, continue
    }
  }
}

async function waitForPageReady(
  page: import('@playwright/test').Page,
  apiPatterns?: Array<string | RegExp>
) {
  if (apiPatterns) {
    await Promise.all(apiPatterns.map(pattern => waitForApiCompletion(page, pattern)));
  }
  await waitForNetworkIdle(page);
  await waitForLoadingComplete(page);
}
```

**C. UI Login Helper (MANDATORY):**
Catatan penting: Ganti semua selector di contoh ini dengan selector yang sudah diverifikasi via MCP (prefer `data-testid`). Jangan gunakan label/nama tombol asumtif bila tidak cocok di aplikasi Anda.
```typescript
async function uiLogin(page: import('@playwright/test').Page) {
  const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
  const AUTH_EMAIL = process.env.AUTH_EMAIL || process.env.TEST_EMAIL!;
  const AUTH_PASSWORD = process.env.AUTH_PASSWORD || process.env.TEST_PASSWORD!;

  await page.goto(BASE_URL + '/auth/login'); // Verifikasi route dari real codebase
  
  const loginPattern = DISCOVERED_PATTERNS.login;
  if (!loginPattern) {
    throw new Error('Login API pattern belum ditemukan dari MCP.');
  }

  const loginResp = waitForApiCompletion(page, loginPattern);
  // TODO(verified): ganti selector berikut oleh hasil verifikasi MCP
  // Prefer: page.getByTestId('login-email'), page.getByTestId('login-password'), dst.
  await page.getByLabel('Email').fill(AUTH_EMAIL); // placeholder
  await page.getByLabel('Password').fill(AUTH_PASSWORD); // placeholder
  await page.getByRole('button', { name: /sign in|login/i }).click(); // placeholder
  
  await loginResp;
  await waitForNetworkIdle(page);
  
  // Verifikasi sukses login (fallback dua locator, kompatibel lintas versi Playwright)
  try {
    // TODO(verified): ganti dengan selector terverifikasi (prefer data-testid)
    await expect(page.getByTestId('user-menu')).toBeVisible({ timeout: 3000 });
  } catch {
    await expect(page.getByRole('button', { name: /profile|user/i })).toBeVisible(); // placeholder
  }
}
```

#### E.3b. Inject Login di beforeEach (jika perlu autentikasi)
Jika Preconditions pada skenario menyebut butuh state login (mis. "Logged in as"), WAJIB tambahkan `beforeEach` yang memanggil `uiLogin(page)` di file yang dihasilkan. Contoh:

```typescript
import { test, expect } from '@playwright/test';

test.describe('<Feature> / <Scenario> (auth required)', () => {
  test.beforeEach(async ({ page }) => {
    await uiLogin(page); // menggunakan AUTH_EMAIL & AUTH_PASSWORD dari ENV
  });

  test('should <hasil utama> setelah login', async ({ page }) => {
    await page.goto((process.env.BASE_URL || 'http://localhost:3000') + '<route>');
    // ...lanjut interaksi & asersi
  });
});
```

#### E.4. Assertion Rules

- Visibility/state/url: `toBeVisible/Hidden`, `toBeDisabled`, `toHaveValue`, `toHaveURL`.
- Content: gunakan `data-testid`/role, hindari `getByText` untuk konten dinamis.
- Error: asersi teks error persis hasil MCP.
- SPA: tunggu `networkidle` + loading selesai; validasi response penting via `waitForResponse` bila perlu.

Minimum: ≥1 assertion per test + validasi API completion untuk SPA.

#### E.5. File Template

Gunakan kerangka standar di `templates/test-file.md` sebagai referensi pembuatan file `.spec.ts`. Ganti placeholder dan selector dengan hasil verifikasi MCP (prefer `data-testid`/role/label). Jangan menyalin label/tulisan tombol asumtif.

#### E.6. Code Quality Standards
- TypeScript strict mode compatible
- Async/await (no `.then()` chains)
- ESLint + Prettier compliant
- Meaningful test descriptions
- No hardcoded data
- **NO magic timeouts** - Use API completion strategies

**AVOID (Bad Practices):**
```typescript
// ❌ DON'T - Arbitrary timeouts
await page.waitForTimeout(3000);

// ❌ DON'T - Hardcoded API patterns
const apiPromise = page.waitForResponse(/\/api\/auth\/login/);
```

**USE (Best Practices):**
```typescript
// ✅ DO - Dynamically discovered patterns
const apiPromise = page.waitForResponse(DISCOVERED_PATTERNS.login);
await page.getByRole('button', { name: 'Login' }).click();
await apiPromise;
await page.waitForLoadState('networkidle');

// ✅ DO - Universal loading state detection
await waitForLoadingComplete(page);

// ✅ DO - Page readiness check
await waitForPageReady(page, [DISCOVERED_PATTERNS.login]);
```

---

### F. Simpan & Output

#### F.1. File Naming & Structure
Policy: **1 test-scenario = 1 file**

**Naming:** `tests/{feature}/{kebab-case-scenario}.spec.ts`
- Contoh: `tests/auth/login-success.spec.ts`
- Contoh: `tests/user/crud-user.spec.ts`

**Directory Structure:**
```
tests/
├── .env.example              # Generated env template
├── auth/
│   ├── login-success.spec.ts
│   └── login-invalid-credentials.spec.ts
├── user/
│   └── crud-user.spec.ts
```

#### F.2. Confirm & Write
1. Konfirmasi path file: `tests/{feature}/{kebab-case-scenario}.spec.ts`
2. Tulis file setelah approval
3. Update `tests/.env.example`:
   - **Hanya menambah kunci baru**
   - **Jangan hapus yang sudah ada**
 - Format:
     ```env
     # Base Configuration
     BASE_URL=http://localhost:3000
     
     # Authentication
     AUTH_EMAIL=test@example.com
     AUTH_PASSWORD=Test123!@#
     
     # Feature-specific (if needed)
     # API_KEY=your-api-key
     ```
4. Keamanan: Jangan commit kredensial asli; gunakan placeholder di `.env.example`.

#### F.3. Deliverables
- ✅ Verified `.spec.ts` file(s) di `tests/*/` (selectors verified via MCP)
- ✅ Updated `tests/.env.example` (append missing keys only)
- ✅ Embedded comments untuk discovered selectors/API patterns
- ✅ Optional: offer to run via `/venturo-e2e-web:run`

---

## Fallback & Error Handling

### Plan File Issues
- **Backlog tabel rusak/kolom kurang:** Minta perbaiki atau isi minimal interaktif (ID, Title, Component Path, Route) untuk skenario terpilih.
- **Missing environment/references di YAML frontmatter:** Tanya apakah perlu dikumpulkan sekarang (optional) atau lanjut.

### Selector Issues
- **Path/selector tidak jelas:** Minta snippet/scan repo → revisi.
- **Selector gagal verifikasi MCP:** Usulkan alternatif atau TODO sementara (dengan approval).

### File System Issues
- **Folder `tests/` belum ada:** Minta izin membuat.
- **`.env.example` tidak ada:** Buat baru.
- **`.env.example` sudah ada:** Hanya append kunci yang hilang, **jangan hapus existing**.

### API Discovery Issues
- **Tidak ada API calls terdeteksi:** Warn dan gunakan fallback `waitForNetworkIdle()` only.
- **Multiple API patterns untuk satu action:** Document semua dan gunakan `Promise.all()`.

---

## Penutup

Setelah generation selesai:
1. Konfirmasi: "Test file tersimpan di `tests/{feature}/{scenario}.spec.ts` dan siap dijalankan."
2. Highlight unresolved issues jika ada (selector TODO, missing API patterns, dll).
3. Tawarkan: "Mau langsung jalankan test-nya via `/venturo-e2e-web:run`?"

**Kompatibilitas:** Diselaraskan dengan `plan-v2`. Jangan ubah heading "## Scenario Backlog" dan urutan kolom tabel agar parsing generator tetap akurat.
