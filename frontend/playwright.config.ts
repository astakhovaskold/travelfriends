import {defineConfig} from '@playwright/test';

const production = process.env.FRONTEND_TARGET === 'production';
const baseURL = production ? 'http://127.0.0.1:5174' : 'http://127.0.0.1:5173';
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  workers: process.env.CI ? 2 : 4,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    [
      'list',
    ],
    [
      'html',
      {
        open: 'never',
        outputFolder:
          process.env.PLAYWRIGHT_HTML_OUTPUT_DIR ||
          `playwright-report/${process.env.FRONTEND_TARGET || 'solid'}`,
      },
    ],
  ],
  updateSnapshots: 'none',
  snapshotPathTemplate:
    '{testDir}/snapshots/{platform}/{projectName}/{arg}{ext}',
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      maxDiffPixels: 0,
    },
  },
  use: {
    baseURL,
    locale: 'en-GB',
    timezoneId: 'UTC',
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        channel: 'chromium',
      },
    },
    {
      name: 'webkit',
      use: {
        browserName: 'webkit',
      },
    },
  ],
  webServer: {
    command: production
      ? 'ENV_FILE=/dev/null DATABASE_URL=sqlite:///:memory: ../.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 5174'
      : 'npm run dev',
    url: baseURL + (production ? '/next/' : '/assets-app/'),
    reuseExistingServer: !process.env.CI,
  },
});
