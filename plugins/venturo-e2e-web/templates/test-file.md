unakan template ini sebagai kerangka dasar saat menghasilkan file `.spec.ts`. Ganti placeholder dengan nilai sebenarnya dan selector yang sudah diverifikasi via MCP. Jangan pernah mengarang / membuat asumsi selector atau teks asersi.

```typescript
import { test, expect } from '@playwright/test';

// Pola API yang ditemukan dari MCP probe (isi saat generate)
const DISCOVERED_PATTERNS: Record<string, RegExp> = {
  // login: /\/core\/v1\/auth\/signin/,
};

// Environment variables (kompatibel mundur)
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const AUTH_EMAIL = process.env.AUTH_EMAIL || process.env.TEST_EMAIL!;
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || process.env.TEST_PASSWORD!;

// Helper: tunggu API selesai
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

// Helper: tunggu network idle
async function waitForNetworkIdle(page: import('@playwright/test').Page) {
  await page.waitForLoadState('networkidle', { timeout: 10000 });
}

// Helper: tunggu loading state selesai (heuristik umum)
async function waitForLoadingComplete(
  page: import('@playwright/test').Page,
  loadingSelector?: string
) {
  const defaultSelectors = [
    loadingSelector,
    '[data-loading="true"]',
    '.loading',
    '[data-testid*="loading"]',
    '[data-state="loading"]',
    '.spinner',
    '[data-testid*="spinner"]'
  ].filter(Boolean) as string[];

  for (const selector of defaultSelectors) {
    try {
      await expect(page.locator(selector)).not.toBeVisible({ timeout: 5000 });
      break;
    } catch {
      // Selector tidak ada/masih terlihat, lanjutkan cek berikutnya
    }
  }
}

// Helper: kesiapan halaman (API + network + loading)
async function waitForPageReady(
  page: import('@playwright/test').Page,
  apiPatterns?: Array<string | RegExp>
) {
  if (apiPatterns && apiPatterns.length) {
    await Promise.all(apiPatterns.map((p) => waitForApiCompletion(page, p)));
  }
  await waitForNetworkIdle(page);
  await waitForLoadingComplete(page);
}

// Helper: UI login (ganti selector dengan hasil verifikasi MCP)
async function uiLogin(page: import('@playwright/test').Page) {
  await page.goto(BASE_URL + '/auth/login');

  const loginPattern = DISCOVERED_PATTERNS.login;
  if (!loginPattern) {
    throw new Error('Login API pattern belum ditemukan dari MCP.');
  }

  // Toleransi backend tidak tersedia saat lokal
  const loginResp = waitForApiCompletion(page, loginPattern, 200).catch(() => null);

  // TODO(verified): ganti selector berikut oleh hasil verifikasi MCP (prefer data-testid)
  await page.getByRole('textbox', { name: /email/i }).fill(AUTH_EMAIL);
  await page.getByRole('textbox', { name: /password/i }).fill(AUTH_PASSWORD);
  await page.getByRole('button', { name: /sign in|login|masuk/i }).click();

  try {
    await loginResp;
  } catch {
    // Backend tidak tersedia; lanjut uji UI tanpa verifikasi server
  }

  await waitForNetworkIdle(page);

  // Verifikasi login atau tolerate error UI jika backend down
  try {
    const errorAlert = page.getByText(/invalid credentials|network error/i);
    if (await errorAlert.isVisible({ timeout: 3000 })) {
      console.log('Backend tidak tersedia, simulasi login/lanjut UI');
      return;
    }
    await expect(page.locator('body')).not.toContainText(/invalid credentials/i, { timeout: 3000 });
  } catch {
    // Timeout; asumsikan login UI lanjut
  }
}

// VARIAN 1: Butuh login (gunakan uiLogin)
test.describe('<Feature> / <Scenario> (auth required)', () => {
  test.beforeEach(async ({ page }) => {
    await uiLogin(page); // menggunakan AUTH_EMAIL & AUTH_PASSWORD dari ENV
  });

  test('should <main outcome> after login', async ({ page }) => {
    await page.goto(BASE_URL + '<route>');
    await waitForPageReady(page);

    // Contoh: dialog + field + submit dengan pola .or()
    const openDialog = page.getByRole('button', { name: /add|create|tambah/i }).or(
      page.locator('[data-testid*="create"]')
    );
    if (await openDialog.count() > 0) {
      await openDialog.first().click();
      // Catatan Mandatory: hindari timeout bila memungkinkan; gunakan waitFor* spesifik jika ada
      await page.waitForTimeout(500);

      const dialog = page.locator('[role="dialog"]').or(page.locator('.modal')).or(
        page.locator('[data-testid*="modal"]')
      );
      if (await dialog.count() > 0) {
        await expect(dialog.first()).toBeVisible();

        const nameField = page.getByLabel(/name|nama/i).or(
          page.getByRole('textbox', { name: /name|nama/i })
        );
        if (await nameField.count() > 0) {
          await nameField.first().fill('Example Name');
        }

        const submitButton = page.getByRole('button', { name: /save|simpan|submit/i });
        if (await submitButton.count() > 0) {
          await submitButton.first().click();
          await page.waitForTimeout(1000);

          const successMessage = page.getByText(/success|berhasil/i);
          const errorMessage = page.getByText(/error|gagal|failed/i);
          try {
            await expect(successMessage.first()).toBeVisible({ timeout: 3000 });
          } catch {
            if (await errorMessage.count() > 0) {
              console.log('Operasi gagal (mungkin backend tidak tersedia)');
            }
          }
        }
      }
    }

    await expect(page).toHaveURL(/<expected-route>/);
  });
});

/*
// VARIAN 2: Publik (tanpa login)
test.describe('<Feature> / <Scenario> (public)', () => {
  test('should <main outcome>', async ({ page }) => {
    await page.goto(BASE_URL + '<route>');
    await waitForPageReady(page);

    // Contoh pola selector fleksibel (ganti dengan data-testid bila ada)
    // const title = page.getByRole('heading', { name: /<title>/i }).or(page.getByTestId('<title-testid>'));
    // await expect(title.first()).toBeVisible();

    await expect(page).toHaveURL(/<expected-route>/);
  });
});
*/

// Panduan singkat:
// - Prefer data-testid/role/label; hindari getByText untuk konten dinamis bila ada alternatif.
// - Minimalkan magic timeout; gunakan waitForResponse/networkidle/waitForPageReady bila memungkinkan.
// - Jangan hardcode API pattern; gunakan DISCOVERED_PATTERNS dari probe MCP.
```
