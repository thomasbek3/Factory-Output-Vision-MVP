import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from '@playwright/test'

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(frontendDir, '..')
const runId = String(Date.now())
const e2eDataDir = path.join(repoRoot, 'data', 'e2e', runId)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:8080',
    headless: true,
    trace: 'on-first-retry',
    viewport: { width: 1440, height: 1024 },
  },
  webServer: {
    command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8080',
    cwd: repoRoot,
    env: {
      ...process.env,
      FC_DB_PATH: path.join(e2eDataDir, 'factory_counter.e2e.db'),
      FC_DEMO_MODE: '1',
      FC_DEMO_VIDEO_PATH: path.join(repoRoot, 'demo', 'demo_counter.mp4'),
      FC_FRAME_STALL_TIMEOUT_SEC: '30',
      FC_FRONTEND_DIST: path.join(repoRoot, 'frontend', 'dist'),
      FC_HEALTH_SAMPLE_INTERVAL_SEC: '0.1',
      FC_LOG_DIR: path.join(e2eDataDir, 'logs'),
      FC_PERSON_DETECT_ENABLED: '0',
    },
    reuseExistingServer: false,
    timeout: 120_000,
    url: 'http://127.0.0.1:8080/dashboard',
  },
  workers: 1,
})
