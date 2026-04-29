import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

const roiPayload = {
  roi_polygon: [
    { x: 0.1, y: 0.15 },
    { x: 0.9, y: 0.15 },
    { x: 0.9, y: 0.85 },
    { x: 0.1, y: 0.85 },
  ],
}

const linePayload = {
  p1: { x: 0.45, y: 0.12 },
  p2: { x: 0.45, y: 0.88 },
  direction: 'both',
}

const directionalLinePayload = {
  ...linePayload,
  direction: 'p1_to_p2',
}

async function postOk(request: APIRequestContext, url: string, payload?: object): Promise<void> {
  const response = await request.post(url, { data: payload })
  expect(response.ok(), `${url} should succeed`).toBeTruthy()
}

async function getConfig(
  request: APIRequestContext,
): Promise<{ line: { direction: string } | null; roi_polygon: Array<{ x: number; y: number }> | null }> {
  const response = await request.get('/api/config')
  expect(response.ok(), '/api/config should succeed').toBeTruthy()
  return (await response.json()) as { line: { direction: string } | null; roi_polygon: Array<{ x: number; y: number }> | null }
}

async function resetRuntime(request: APIRequestContext): Promise<void> {
  await postOk(request, '/api/control/monitor/stop')
  await postOk(request, '/api/control/reset_calibration')
  await postOk(request, '/api/config/operator_zone', { enabled: false })
}

async function seedConfiguredLine(request: APIRequestContext): Promise<void> {
  await postOk(request, '/api/config/roi', roiPayload)
  await postOk(request, '/api/config/line', linePayload)
  await postOk(request, '/api/config/operator_zone', { enabled: false })
}

async function waitForStatusOk(request: APIRequestContext, url: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const response = await request.get(url)
    if (response.ok()) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function clickNormalized(locator: Locator, xRatio: number, yRatio: number): Promise<void> {
  const box = await locator.boundingBox()
  if (!box) {
    throw new Error('Snapshot frame bounding box not available')
  }
  await locator.click({
    position: {
      x: box.width * xRatio,
      y: box.height * yRatio,
    },
  })
}

async function expectSnapshotSrc(page: Page, fragment: string): Promise<void> {
  const image = page.locator('.live-snapshot-frame img').first()
  await expect
    .poll(async () => image.getAttribute('src'))
    .toContain(fragment)
}

async function expectVideoSrc(page: Page, fragment: string): Promise<void> {
  const video = page.locator('.live-snapshot-frame video').first()
  await expect(video).toBeVisible()
  await expect
    .poll(async () => video.getAttribute('src'))
    .toContain(fragment)
}

async function expectNotice(page: Page, message: RegExp): Promise<void> {
  await expect(page.locator('.notice-banner').filter({ hasText: message }).first()).toBeVisible()
}

test.describe.configure({ mode: 'serial' })

test.beforeEach(async ({ request }) => {
  await resetRuntime(request)
})

test('wizard completes core demo setup interactions and starts calibration', async ({ page, request }) => {
  await page.goto('/wizard')

  const wizardHeaderActions = page.locator('.wizard-main .inline-actions')
  const stepBody = page.locator('.wizard-step-body')
  await expect(page.getByRole('heading', { level: 1, name: /Setup now lives in React/i })).toBeVisible()

  await wizardHeaderActions.getByRole('button', { name: 'Next' }).click()
  await wizardHeaderActions.getByRole('button', { name: 'Next' }).click()

  await expect(page.getByText(/Demo mode is active\. Camera details are optional/i)).toBeVisible()
  await page.getByRole('button', { name: 'Save camera settings' }).click()

  await expect(page.getByRole('heading', { level: 2, name: 'Test Camera' })).toBeVisible()
  await stepBody.getByRole('button', { exact: true, name: 'Test camera' }).click()
  await expectNotice(page, /Demo video connected/i)

  await stepBody.getByRole('button', { exact: true, name: 'Next' }).click()
  await waitForStatusOk(request, '/api/snapshot')

  const outputArea = page.getByLabel('Output Area')
  await clickNormalized(outputArea, 0.2, 0.2)
  await clickNormalized(outputArea, 0.8, 0.2)
  await clickNormalized(outputArea, 0.8, 0.8)
  await clickNormalized(outputArea, 0.2, 0.8)
  await stepBody.getByRole('button', { exact: true, name: 'Save output area' }).click()
  await expectNotice(page, /Output area saved\./i)
  await stepBody.getByRole('button', { exact: true, name: 'Next' }).click()

  const countLine = page.getByLabel('Count Line')
  await clickNormalized(countLine, 0.48, 0.2)
  await clickNormalized(countLine, 0.48, 0.8)
  await stepBody.getByRole('button', { exact: true, name: 'Save count line' }).click()
  await expectNotice(page, /Count line saved\./i)
  await stepBody.getByRole('button', { exact: true, name: 'Next' }).click()

  await stepBody.getByRole('button', { exact: true, name: 'Skip operator zone' }).click()
  await expectNotice(page, /Operator zone disabled\./i)
  await stepBody.getByRole('button', { exact: true, name: 'Next' }).click()

  await stepBody.getByRole('button', { exact: true, name: 'Start calibrating' }).click()
  await expectNotice(page, /Calibration started\./i)
  await expect(page.getByText(/Calibration progress/i)).toBeVisible()
  await expect(page.getByText(/Current backend state/i)).toBeVisible()
})

test('wizard demo flow allows advancing past test camera without rerunning a manual probe', async ({ page }) => {
  await page.goto('/wizard')

  const wizardHeaderActions = page.locator('.wizard-main .inline-actions')
  const stepBody = page.locator('.wizard-step-body')

  await wizardHeaderActions.getByRole('button', { name: 'Next' }).click()
  await wizardHeaderActions.getByRole('button', { name: 'Next' }).click()
  await page.getByRole('button', { name: 'Save camera settings' }).click()

  await expect(page.getByRole('heading', { level: 2, name: 'Test Camera' })).toBeVisible()
  await expect(stepBody.getByRole('button', { exact: true, name: 'Next' })).toBeEnabled()
  await expect(page.getByText(/Live video is already reaching the backend/i)).toBeVisible()

  await stepBody.getByRole('button', { exact: true, name: 'Next' }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Mark Output Area' })).toBeVisible()
})

test('wizard can clear a saved ROI and resave it cleanly', async ({ page, request }) => {
  await seedConfiguredLine(request)
  await page.goto('/wizard')

  await page.getByRole('button', { name: /Mark Output Area/i }).click()
  await expect(page.getByText(/What the backend currently has saved\./i)).toBeVisible()
  await expect(page.getByText(/^4 points$/)).toBeVisible()

  await page.getByRole('button', { name: 'Clear saved area' }).click()
  await expectNotice(page, /Output area cleared\./i)
  await expect(page.getByText(/^Missing$/)).toBeVisible()

  const outputArea = page.getByLabel('Output Area')
  await clickNormalized(outputArea, 0.15, 0.25)
  await clickNormalized(outputArea, 0.85, 0.25)
  await clickNormalized(outputArea, 0.85, 0.75)
  await clickNormalized(outputArea, 0.15, 0.75)
  await expect(page.getByText(/Draft only\./i)).toBeVisible()
  await page.getByRole('button', { name: 'Save output area' }).click()
  await expectNotice(page, /Output area saved\./i)
  await expect(page.getByText(/^4 points$/)).toBeVisible()
})

test('dashboard controls trigger calibration and monitoring state changes', async ({ page, request }) => {
  await seedConfiguredLine(request)

  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  await page.getByRole('button', { name: 'Start calibration' }).click()
  await expectNotice(page, /Calibration started\./i)

  await page.getByRole('button', { name: 'Stop monitoring' }).click()
  await expectNotice(page, /Monitoring stopped\./i)
})

test('dashboard and troubleshooting expose runtime versus proof-backed totals', async ({ page, request }) => {
  await seedConfiguredLine(request)
  await postOk(request, '/api/control/adjust_count', { delta: 3 })

  await page.goto('/dashboard')
  await expect(page.getByText(/^Runtime Total$/)).toBeVisible()
  await expect(page.getByText(/^Proof-Backed$/)).toBeVisible()
  await expect(page.getByText(/^Runtime-Inferred$/)).toBeVisible()
  await expect(page.getByText(/^3$/).first()).toBeVisible()
  await expect(page.getByText(/^0$/).first()).toBeVisible()

  await page.goto('/troubleshooting')
  await expect(page.getByText(/^Runtime Total$/)).toBeVisible()
  await expect(page.getByText(/^Proof-Backed$/)).toBeVisible()
  await expect(page.getByText(/^Runtime-Inferred$/)).toBeVisible()
})

test('dashboard shows concrete counting hints when monitoring is running but counts stay at zero', async ({ page, request }) => {
  await postOk(request, '/api/config/roi', roiPayload)
  await postOk(request, '/api/config/line', directionalLinePayload)

  await page.goto('/dashboard')
  await page.getByRole('button', { name: 'Start monitoring' }).click()

  await expect(page.getByRole('heading', { level: 3, name: 'Counting Checks' })).toBeVisible()
  await expect(page.getByText(/Zero counts means no tracked part has crossed the saved line yet\./i)).toBeVisible()
  await expect(page.getByText(/Current line direction is Start point to end point only\./i)).toBeVisible()
})

test('troubleshooting switches between live and debug snapshot views', async ({ page, request }) => {
  await seedConfiguredLine(request)
  await postOk(request, '/api/control/monitor/start')
  await waitForStatusOk(request, '/api/diagnostics/snapshot/debug?view=tracks')

  await page.goto('/troubleshooting')
  await expect(page.getByRole('heading', { level: 2, name: 'Camera And Debug Views' })).toBeVisible()

  await page.getByRole('button', { name: 'Mask view' }).click()
  await expect(page.getByText(/foreground mask and detected blobs/i)).toBeVisible()
  await expectSnapshotSrc(page, 'view=mask')

  await page.getByRole('button', { name: 'Tracks view' }).click()
  await expect(page.getByText(/detection boxes and track labels/i)).toBeVisible()
  await expectSnapshotSrc(page, 'view=tracks')

  await page.getByRole('button', { name: 'ROI view' }).click()
  await expect(page.getByText(/masked counting area/i)).toBeVisible()
  await expectSnapshotSrc(page, 'view=roi')

  await page.getByRole('button', { name: 'Live view' }).click()
  await expect(page.getByText(/Browser preview plays the active demo file directly/i)).toBeVisible()
  await expectVideoSrc(page, '/api/control/demo/videos/active/content')
  await expect(page.locator('.live-snapshot-frame svg.live-overlay-svg')).toBeVisible()
  await expect(page.locator('.live-snapshot-frame svg.live-overlay-svg polygon')).toHaveCount(1)
  await expect(page.locator('.live-snapshot-frame svg.live-overlay-svg line')).toHaveCount(1)
})

test('troubleshooting lets operators edit ROI and count line directly on the live panel', async ({ page, request }) => {
  await postOk(request, '/api/config/roi/clear')
  await postOk(request, '/api/config/line/clear')

  await page.goto('/troubleshooting')
  await expect(page.getByRole('heading', { level: 2, name: 'Camera And Debug Views' })).toBeVisible()

  const liveFrame = page.locator('.live-snapshot-frame').first()
  await expect(liveFrame).toBeVisible()

  await page.getByRole('button', { name: 'Edit output area' }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Edit Output Area' })).toBeVisible()

  await clickNormalized(liveFrame, 0.2, 0.25)
  await clickNormalized(liveFrame, 0.78, 0.25)
  await clickNormalized(liveFrame, 0.78, 0.74)
  await clickNormalized(liveFrame, 0.2, 0.74)
  await page.getByRole('button', { name: 'Save output area' }).click()
  await expectNotice(page, /Output area saved from live view\./i)

  const configAfterRoi = await getConfig(request)
  expect(configAfterRoi.roi_polygon).toHaveLength(4)
  await expect(page.locator('.live-snapshot-frame svg.live-overlay-svg polygon')).toHaveCount(1)

  await page.getByRole('button', { name: 'Edit count line' }).click()
  await expect(page.getByRole('heading', { level: 2, name: 'Edit Count Line' })).toBeVisible()
  await page.getByLabel('Count direction').selectOption('top_to_bottom')

  await clickNormalized(liveFrame, 0.5, 0.23)
  await clickNormalized(liveFrame, 0.5, 0.76)
  await page.getByRole('button', { name: 'Save count line' }).click()
  await expectNotice(page, /Count line saved from live view\./i)

  const configAfterLine = await getConfig(request)
  expect(configAfterLine.line?.direction).toBe('top_to_bottom')
  await expect(page.locator('.live-snapshot-frame svg.live-overlay-svg line')).toHaveCount(1)
})
