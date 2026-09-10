import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ...(process.env.E2E_BASIC_AUTH_USER && process.env.E2E_BASIC_AUTH_PASSWORD ? { httpCredentials: { username: process.env.E2E_BASIC_AUTH_USER, password: process.env.E2E_BASIC_AUTH_PASSWORD } } : {}),
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } } : {}),
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
