import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

test('keeps the profiling shell isolated until the completed workspace is ready', async ({ page }) => {
  await page.goto('/');
  const health = await page.request.get('/api/health');
  const healthBody = await health.json() as { status: string; build_sha: string; release_manifest: { source_sha: string; assets: Record<string, string> } | null };
  expect(healthBody.status).toBe('ok');
  const frontendSha = await page.locator('html').getAttribute('data-build-sha');
  expect(frontendSha).toMatch(/^[0-9a-f]{40}$/);
  // Local E2E serves Vite source while the API process may come from the last
  // release image; release SHA equality is asserted by the authenticated DEV gate.
  expect(healthBody.build_sha).toMatch(/^[0-9a-f]{40}$/);
  expect(healthBody.release_manifest?.source_sha).toBe(healthBody.build_sha);
  expect(Object.keys(healthBody.release_manifest?.assets ?? {})).not.toHaveLength(0);
  await expect(page.getByRole('heading', { name: 'Bring your dataset' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-build-sha', /.+/);
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toHaveCount(0);

  // Force the asynchronous profile branch even when the local worker completes
  // a tiny fixture before the upload response returns.
  await page.route('**/api/runs/upload', async route => {
    const response = await route.fetch();
    const profile = await response.json() as Record<string, unknown>;
    await route.fulfill({ response, json: { ...profile, profile_status: 'sampled' } });
  });
  let releaseProfileStatus: (() => void) | undefined;
  await page.route('**/profile/status**', async route => {
    await new Promise<void>(resolve => { releaseProfileStatus = resolve; });
    await route.continue();
  });
  await page.locator('input[type="file"]').setInputFiles({ name: 'scope.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await expect(page.getByRole('heading', { name: 'Your workspace is taking shape.' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toHaveCount(0);
  await expect.poll(() => Boolean(releaseProfileStatus)).toBe(true);
  releaseProfileStatus?.();
  await page.unroute('**/profile/status**');

  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Executive Hub' })).toBeVisible();
  await expect(page.locator('.workspace-grid')).toBeVisible();
  await expect(page.locator('.executive-chart-grid')).toBeVisible();

  await page.getByRole('button', { name: 'Deep Dive Lab' }).click();
  await expect(page.getByRole('heading', { name: 'Deep Dive Lab' })).toBeVisible();
});
