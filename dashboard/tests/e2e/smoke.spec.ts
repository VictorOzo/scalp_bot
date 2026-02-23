import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('http://127.0.0.1:8000/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.endsWith('/auth/login') && method === 'POST') {
      await route.fulfill({
        status: 200,
        headers: { 'content-type': 'application/json', 'set-cookie': 'sb_auth=fake; HttpOnly; Path=/' },
        body: JSON.stringify({ username: 'admin', role: 'admin' })
      });
      return;
    }
    if (url.endsWith('/auth/logout')) {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ok: true }) });
      return;
    }
    if (url.includes('/settings') && method === 'GET') {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ pairs: ['EUR_USD'] }) });
      return;
    }
    if (url.includes('/status')) {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ mode: 'OFFLINE', last_cycle_ts_utc: '2025-01-01T00:00:00+00:00', is_stale: true, stale_threshold_seconds: 30 }) });
      return;
    }
    if (url.includes('/gates')) {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify([{ allowed: false, reasons: ['paused'] }]) });
      return;
    }
    if (url.includes('/trades?')) {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ items: [{ id: 1, pair: 'EUR_USD', side: 'BUY', opened_ts_utc: '2025-01-01T00:00:00+00:00' }], next_cursor: null }) });
      return;
    }
    if (url.includes('/exports/trades.xlsx')) {
      await route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'content-disposition': 'attachment; filename="trades.xlsx"'
        },
        body: 'fake-xlsx'
      });
      return;
    }
    if (url.endsWith('/commands') && method === 'POST') {
      await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ id: 12, status: 'PENDING' }) });
      return;
    }

    await route.fulfill({ status: 404, body: 'not mocked' });
  });
});

test('login -> overview -> trades export -> pause command', async ({ page }) => {
  await page.goto('/login');
  await page.getByTestId('username').fill('admin');
  await page.getByTestId('password').fill('admin-pass');
  await page.getByTestId('login-submit').click();

  await expect(page.getByTestId('overview-page')).toBeVisible();
  await expect(page.getByTestId('status-mode')).toContainText('OFFLINE');
  await expect(page.getByTestId('pair-card-EUR_USD')).toBeVisible();
  await expect(page.getByTestId('stale-warning')).toBeVisible();

  await page.goto('/trades');
  await expect(page.getByTestId('trades-page')).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByTestId('export-trades').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain('trades.xlsx');

  await page.goto('/overview');
  page.once('dialog', (d) => d.dismiss());
  await page.getByTestId('pause-EUR_USD').click();
});
