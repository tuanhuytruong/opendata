import { expect, Page, test } from '@playwright/test';

const csv = [
  'sale_date,division,net_sales,quantity',
  '2026-01-01,North,100,1',
  '2026-01-02,South,200,2',
  '2026-02-01,North,300,3',
].join('\n');

async function openBuilder(page: Page) {
  await page.goto('/');
  const upload = page.waitForResponse(response => response.url().endsWith('/api/runs/upload') && response.request().method() === 'POST');
  await page.locator('input[type="file"]').setInputFiles({
    name: 'report-builder-authoring.csv', mimeType: 'text/csv', buffer: Buffer.from(csv),
  });
  const runId = (await (await upload).json() as { run_id: string }).run_id;
  await expect(page.getByRole('navigation', { name: 'Workspace navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Custom Report' }).click();
  await expect(page.locator('.report-builder')).toBeVisible();
  page.once('dialog', dialog => void dialog.accept());
  await page.locator('.template-choice').first().click();
  await expect(page.locator('.report-save-saved')).toBeVisible();
  return runId;
}

test('authors text, renames a page, and keeps preview read-only', async ({ page }) => {
  await openBuilder(page);

  await page.getByRole('button', { name: 'text', exact: true }).click();
  const editor = page.locator('.report-rich-editor').last();
  await editor.fill('Evidence summary\nSecond paragraph');
  await editor.blur();
  await expect(editor).toContainText('Second paragraph');

  await page.getByRole('button', { name: 'Pages', exact: true }).click();
  const pageName = page.locator('.report-page-manager-row input').first();
  await pageName.fill('Board summary');
  await pageName.blur();
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Board summary', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await expect(page.locator('.report-canvas-preview')).toBeVisible();
  await expect(page.locator('.report-library')).toHaveCount(0);
  await expect(page.locator('.report-inspector')).toHaveCount(0);
  await expect(page.locator('.report-rich-editor[contenteditable="false"]').first()).toBeVisible();
});

test('exports reader-facing HTML without internal page or block metadata', async ({ page }) => {
  const runId = await openBuilder(page);
  const exportResponse = page.waitForResponse(response => response.url().endsWith('/custom-report/exports') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Export HTML', exact: true }).click();
  const payload = await (await exportResponse).json() as { export_id: string; revision: number };
  expect(payload.revision).toBeGreaterThanOrEqual(1);

  const htmlResponse = await page.request.get(`/api/runs/${runId}/custom-report/exports/${payload.export_id}`);
  expect(htmlResponse.ok()).toBe(true);
  const html = await htmlResponse.text();
  expect(html).toContain('<h1>');
  expect(html).not.toContain('Authored report');
  expect(html).not.toContain('data-block-id');
  expect(html).not.toContain('data-page-id');
  expect(html).not.toContain('--x:');
  await expect(page.getByText(new RegExp(`Exported revision ${payload.revision}`))).toBeVisible();
});
