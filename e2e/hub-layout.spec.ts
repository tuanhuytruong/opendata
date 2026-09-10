import { expect, test } from '@playwright/test';

const csv = [
  'sale_date,division,channel,net_sales,quantity',
  '2026-01-01,North,Online,100,1',
  '2026-01-02,South,Retail,200,2',
  '2026-01-03,North,Partner,300,3',
  '2026-02-01,South,Online,400,4',
  '2026-02-02,North,Retail,500,5',
].join('\n');

async function openWorkspace(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles({ name: 'layout.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await expect(page.getByRole('heading', { name: 'Executive Hub' })).toBeVisible();
  await expect(page.locator('.executive-chart-grid')).toBeVisible();
}

test('keeps Executive Hub chart source order in a balanced desktop grid without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openWorkspace(page);
  const geometry = await page.locator('.executive-chart-grid').evaluate(grid => {
    const style = getComputedStyle(grid);
    const children = Array.from(grid.children).map(child => {
      const rect = child.getBoundingClientRect();
      return { left: Math.round(rect.left), top: Math.round(rect.top), width: Math.round(rect.width) };
    });
    return { columns: style.gridTemplateColumns.split(' ').length, overflow: grid.scrollWidth > grid.clientWidth, children };
  });
  expect(geometry.columns).toBe(2);
  expect(geometry.overflow).toBe(false);
  expect(geometry.children.length).toBeGreaterThanOrEqual(2);
  expect(geometry.children[0].top).toBe(geometry.children[1].top);
  expect(geometry.children[0].left).toBeLessThan(geometry.children[1].left);
});

test('stacks Executive Hub artifacts into one source-ordered column below the compact breakpoint', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 900 });
  await openWorkspace(page);
  const geometry = await page.locator('.executive-chart-grid').evaluate(grid => {
    const style = getComputedStyle(grid);
    const children = Array.from(grid.children).map(child => {
      const rect = child.getBoundingClientRect();
      return { left: Math.round(rect.left), top: Math.round(rect.top) };
    });
    return { columns: style.gridTemplateColumns.split(' ').length, overflow: grid.scrollWidth > grid.clientWidth, children };
  });
  expect(geometry.columns).toBe(1);
  expect(geometry.overflow).toBe(false);
  expect(geometry.children.length).toBeGreaterThanOrEqual(2);
  expect(geometry.children[0].top).toBeLessThan(geometry.children[1].top);
});
