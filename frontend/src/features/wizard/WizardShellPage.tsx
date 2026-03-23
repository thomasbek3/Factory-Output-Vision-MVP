import { startTransition, useEffect, useMemo, useState } from 'react'
import type { ReactElement } from 'react'

import { apiClient } from '../../shared/api/client.ts'
import type {
  CameraConfigRequest,
  CameraTestResponse,
  ConfigResponse,
  DiagnosticsResponse,
  Point,
  StatusResponse,
  StreamProfile,
} from '../../shared/api/types.ts'
import { StatusPill } from '../../shared/components/StatusPill.tsx'
import { SnapshotAnnotator } from './components/SnapshotAnnotator.tsx'

type WizardStepId = 'welcome' | 'mounting' | 'camera' | 'test' | 'roi' | 'operator' | 'calibration'
type FeedbackTone = 'info' | 'success' | 'error'

type StepDefinition = {
  id: WizardStepId
  title: string
  eyebrow: string
  description: string
}

type CameraFormState = {
  camera_ip: string
  camera_username: string
  camera_password: string
  stream_profile: StreamProfile
}

const wizardSteps: StepDefinition[] = [
  { id: 'welcome', title: 'Welcome', eyebrow: 'Step 0', description: 'Check the basics before touching setup.' },
  {
    id: 'mounting',
    title: 'Camera Mounting Guide',
    eyebrow: 'Step 0.5',
    description: 'Bad camera position causes more misses than bad tuning.',
  },
  {
    id: 'camera',
    title: 'Connect Camera',
    eyebrow: 'Step 1',
    description: 'Save the camera address and login details the backend will use.',
  },
  {
    id: 'test',
    title: 'Test Camera',
    eyebrow: 'Step 1.5',
    description: 'Make sure the backend can actually read video from the chosen source.',
  },
  {
    id: 'roi',
    title: 'Mark Output Area',
    eyebrow: 'Step 2',
    description: 'Draw the zone where output accumulates. Objects detected here get counted.',
  },
  {
    id: 'operator',
    title: 'Operator Zone',
    eyebrow: 'Step 3',
    description: 'Optional: only check for an operator when the line slows down.',
  },
  {
    id: 'calibration',
    title: 'Calibration',
    eyebrow: 'Step 4',
    description: 'Run the line normally so the backend can set the baseline rate.',
  },
]

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function hasPolygon(points: Point[] | null | undefined): boolean {
  return Boolean(points && points.length >= 3)
}

function stateGuidance(state: string | undefined): string {
  switch (state) {
    case 'NOT_CONFIGURED':
      return 'Setup still needs saved camera settings and an output area.'
    case 'CALIBRATING':
      return 'Calibration is running. Keep the line moving normally until the baseline is set.'
    case 'RUNNING_YELLOW_RECONNECTING':
      return 'Video is reconnecting. Wait a moment, then refresh the snapshot if it stays stale.'
    case 'RUNNING_RED_STOPPED':
      return 'The backend sees the line as stopped. Check the live view and recent setup steps.'
    case 'RUNNING_YELLOW_DROP':
      return 'Production is slowing down. Review the output area if counts look wrong.'
    case 'RUNNING_GREEN':
      return 'Backend is healthy and ready to monitor with the saved setup.'
    case 'IDLE':
      return 'Setup is saved. Start calibration or monitoring when you are ready.'
    default:
      return 'Save each step in order so the backend keeps a complete setup.'
  }
}

function buildCameraForm(config: ConfigResponse | null): CameraFormState {
  return {
    camera_ip: config?.camera_ip ?? '',
    camera_username: config?.camera_username ?? '',
    camera_password: '',
    stream_profile: config?.stream_profile ?? 'sub',
  }
}

function syncEditorStateFromConfig(
  config: ConfigResponse,
  setOperatorEnabled: (enabled: boolean) => void,
): void {
  setOperatorEnabled(config.operator_zone.enabled)
}

export function WizardShellPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null)
  const [cameraForm, setCameraForm] = useState<CameraFormState>(buildCameraForm(null))
  const [cameraTest, setCameraTest] = useState<CameraTestResponse | null>(null)
  const [cameraTestPassed, setCameraTestPassed] = useState(false)
  const [currentStep, setCurrentStep] = useState<WizardStepId>('welcome')
  const [roiDraft, setRoiDraft] = useState<Point[]>([])
  const [operatorDraft, setOperatorDraft] = useState<Point[]>([])
  const [operatorEnabled, setOperatorEnabled] = useState(false)
  const [snapshotTick, setSnapshotTick] = useState(0)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null)

  const currentStepIndex = wizardSteps.findIndex((step) => step.id === currentStep)
  const isDemoSource = diagnostics?.source_kind === 'demo'
  const liveFeedReady = status?.last_frame_age_sec != null && status.last_frame_age_sec < 5
  const cameraTestComplete = cameraTestPassed || isDemoSource || liveFeedReady

  const completion = useMemo(() => {
    const cameraConfigured = isDemoSource || Boolean(config?.camera_ip && config?.camera_username && config?.camera_password)
    const roiConfigured = hasPolygon(config?.roi_polygon)
    const calibrationComplete = status?.baseline_rate_per_min != null
    return {
      welcome: true,
      mounting: true,
      camera: cameraConfigured,
      test: cameraTestComplete,
      roi: roiConfigured,
      operator: true,
      calibration: calibrationComplete,
    }
  }, [cameraTestComplete, config, isDemoSource, status?.baseline_rate_per_min])

  const completionOrder = wizardSteps.map((step) => completion[step.id])
  const firstIncompleteIndex = completionOrder.findIndex((done) => !done)
  const furthestAvailableIndex =
    firstIncompleteIndex === -1 ? wizardSteps.length - 1 : Math.min(firstIncompleteIndex + 1, wizardSteps.length - 1)
  const stepStateHelp = stateGuidance(status?.state)
  const calibrationProgress = status?.calibration_progress_pct ?? 0
  const calibrationSnapshotUrl = apiClient.snapshotUrl(
    snapshotTick,
    status?.state === 'CALIBRATING' ? 'calibration' : 'default',
  )
  const canAdvanceCurrentStep = currentStep === 'welcome' || currentStep === 'mounting' || currentStep === 'operator'
    ? true
    : completion[currentStep]

  useEffect(() => {
    let active = true

    async function loadInitial(): Promise<void> {
      try {
        const [configResponse, statusResponse, diagnosticsResponse] = await Promise.all([
          apiClient.getConfig(),
          apiClient.getStatus(),
          apiClient.getDiagnostics(),
        ])

        if (!active) {
          return
        }

        startTransition(() => {
          setConfig(configResponse)
          setStatus(statusResponse)
          setDiagnostics(diagnosticsResponse)
          setCameraForm(buildCameraForm(configResponse))
          setRoiDraft([])
          setOperatorDraft([])
          syncEditorStateFromConfig(configResponse, setOperatorEnabled)
          setFeedback(null)
        })
      } catch (error) {
        if (!active) {
          return
        }
        setFeedback({ tone: 'error', message: toMessage(error, 'Unable to load setup data.') })
      }
    }

    void loadInitial()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true

    async function pollStatus(): Promise<void> {
      try {
        const statusResponse = await apiClient.getStatus()
        if (!active) {
          return
        }
        startTransition(() => {
          setStatus(statusResponse)
        })
      } catch (error) {
        if (!active) {
          return
        }
        setFeedback((current) => current ?? { tone: 'error', message: toMessage(error, 'Unable to refresh backend state.') })
      }
    }

    void pollStatus()
    const timer = window.setInterval(() => {
      void pollStatus()
    }, 3000)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (status?.state !== 'CALIBRATING') {
      return
    }
    const timer = window.setInterval(() => {
      setSnapshotTick(Date.now())
    }, 2500)
    return () => {
      window.clearInterval(timer)
    }
  }, [status?.state])

  useEffect(() => {
    if (status?.baseline_rate_per_min == null || config?.baseline_rate_per_min != null) {
      return
    }
    void (async () => {
      try {
        const configResponse = await apiClient.getConfig()
        startTransition(() => {
          setConfig(configResponse)
          setRoiDraft([])
          setOperatorDraft([])
          syncEditorStateFromConfig(configResponse, setOperatorEnabled)
        })
      } catch (error) {
        setFeedback({ tone: 'error', message: toMessage(error, 'Unable to refresh saved setup.') })
      }
    })()
  }, [config?.baseline_rate_per_min, status?.baseline_rate_per_min])

  async function refreshConfig(): Promise<void> {
    try {
      const configResponse = await apiClient.getConfig()
      startTransition(() => {
        setConfig(configResponse)
        setRoiDraft([])
        setOperatorDraft([])
        syncEditorStateFromConfig(configResponse, setOperatorEnabled)
      })
    } catch (error) {
      setFeedback({ tone: 'error', message: toMessage(error, 'Unable to refresh saved setup.') })
    }
  }

  async function refreshStatus(): Promise<void> {
    try {
      const statusResponse = await apiClient.getStatus()
      setStatus(statusResponse)
    } catch (error) {
      setFeedback({ tone: 'error', message: toMessage(error, 'Unable to refresh backend state.') })
    }
  }

  function setSuccess(message: string): void {
    setFeedback({ tone: 'success', message })
  }

  function setError(message: string): void {
    setFeedback({ tone: 'error', message })
  }

  function isStepAvailable(index: number): boolean {
    return index <= furthestAvailableIndex || index <= currentStepIndex
  }

  function goToStep(stepId: WizardStepId): void {
    const index = wizardSteps.findIndex((step) => step.id === stepId)
    if (index === -1 || !isStepAvailable(index)) {
      return
    }
    setCurrentStep(stepId)
  }

  function goNext(): void {
    if (currentStepIndex >= wizardSteps.length - 1 || !canAdvanceCurrentStep) {
      return
    }
    goToStep(wizardSteps[currentStepIndex + 1].id)
  }

  function goBack(): void {
    if (currentStepIndex <= 0) {
      return
    }
    setCurrentStep(wizardSteps[currentStepIndex - 1].id)
  }

  async function handleCameraSave(): Promise<void> {
    if (isDemoSource) {
      setSuccess('Demo mode is active. Camera details are optional for this source.')
      goNext()
      return
    }

    if (!cameraForm.camera_ip || !cameraForm.camera_username || !cameraForm.camera_password) {
      setError('Enter camera IP, username, and password before saving.')
      return
    }

    setBusyAction('camera-save')
    try {
      const payload: CameraConfigRequest = {
        camera_ip: cameraForm.camera_ip.trim(),
        camera_username: cameraForm.camera_username.trim(),
        camera_password: cameraForm.camera_password,
        stream_profile: cameraForm.stream_profile,
      }
      await apiClient.saveCameraConfig(payload)
      await refreshConfig()
      await refreshStatus()
      setCameraForm((current) => ({ ...current, camera_password: '' }))
      setSuccess('Camera settings saved.')
    } catch (error) {
      setError(toMessage(error, 'Unable to save camera settings.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleTestCamera(): Promise<void> {
    setBusyAction('camera-test')
    try {
      const response = await apiClient.testCamera()
      setCameraTest(response)
      setCameraTestPassed(response.ok)
      setFeedback({
        tone: response.ok ? 'success' : 'error',
        message: response.ok ? response.message : response.action_hint ?? response.message,
      })
      setSnapshotTick(Date.now())
    } catch (error) {
      setCameraTestPassed(false)
      setError(toMessage(error, 'Unable to test the camera source.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSaveRoi(): Promise<void> {
    if (roiDraft.length < 3) {
      setError('Draw at least three points to save the output area.')
      return
    }

    setBusyAction('roi-save')
    try {
      await apiClient.saveRoi({ roi_polygon: roiDraft })
      await refreshConfig()
      await refreshStatus()
      setSuccess('Output area saved.')
    } catch (error) {
      setError(toMessage(error, 'Unable to save the output area.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleClearRoi(): Promise<void> {
    setBusyAction('roi-clear')
    try {
      setRoiDraft([])
      await apiClient.clearRoi()
      await refreshConfig()
      await refreshStatus()
      setSuccess('Output area cleared.')
    } catch (error) {
      setError(toMessage(error, 'Unable to clear the output area.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleSaveOperatorZone(): Promise<void> {
    setBusyAction('operator-save')
    try {
      if (!operatorEnabled) {
        await apiClient.saveOperatorZone({ enabled: false })
        await refreshConfig()
        setSuccess('Operator zone disabled.')
        return
      }

      if (operatorDraft.length < 3) {
        setError('Draw at least three points to save the operator zone.')
        return
      }

      await apiClient.saveOperatorZone({ enabled: true, polygon: operatorDraft })
      await refreshConfig()
      setSuccess('Operator zone saved.')
    } catch (error) {
      setError(toMessage(error, 'Unable to save the operator zone.'))
    } finally {
      setBusyAction(null)
    }
  }


  async function handleClearOperatorZone(): Promise<void> {
    setBusyAction('operator-clear')
    try {
      setOperatorDraft([])
      setOperatorEnabled(false)
      await apiClient.clearOperatorZone()
      await refreshConfig()
      setSuccess('Operator zone cleared.')
    } catch (error) {
      setError(toMessage(error, 'Unable to clear the operator zone.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleClearAllGeometry(): Promise<void> {
    setBusyAction('geometry-clear-all')
    try {
      setRoiDraft([])
      setOperatorDraft([])
      setOperatorEnabled(false)
      await Promise.all([apiClient.clearRoi(), apiClient.clearOperatorZone()])
      await refreshConfig()
      await refreshStatus()
      setSuccess('All saved setup geometry cleared.')
    } catch (error) {
      setError(toMessage(error, 'Unable to clear all saved setup geometry.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleStartCalibration(): Promise<void> {
    setBusyAction('calibration-start')
    try {
      const nextStatus = await apiClient.startCalibration()
      setStatus(nextStatus)
      if (nextStatus.state === 'CALIBRATING') {
        setSuccess('Calibration started. Let the line run normally until the baseline is set.')
        return
      }
      setFeedback({ tone: 'info', message: stateGuidance(nextStatus.state) })
    } catch (error) {
      setError(toMessage(error, 'Unable to start calibration.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleResetCalibration(): Promise<void> {
    setBusyAction('calibration-reset')
    try {
      const nextStatus = await apiClient.resetCalibration()
      setStatus(nextStatus)
      await refreshConfig()
      setSuccess('Baseline cleared. Save any drawing changes, then start calibration again.')
    } catch (error) {
      setError(toMessage(error, 'Unable to reset calibration.'))
    } finally {
      setBusyAction(null)
    }
  }

  async function handleStartMonitoring(): Promise<void> {
    setBusyAction('monitor-start')
    try {
      const nextStatus = await apiClient.startMonitoring()
      setStatus(nextStatus)
      setSuccess('Monitoring started.')
    } catch (error) {
      setError(toMessage(error, 'Unable to start monitoring.'))
    } finally {
      setBusyAction(null)
    }
  }

  const sharedOverlays = {
    roi: hasPolygon(config?.roi_polygon)
      ? [{ kind: 'polygon' as const, color: '#1f9d55', label: 'Saved output area', points: config?.roi_polygon ?? [] }]
      : [],
    operator:
      config?.operator_zone.enabled && hasPolygon(config?.operator_zone.polygon)
        ? [
            {
              kind: 'polygon' as const,
              color: '#2563eb',
              label: 'Saved operator zone',
              points: config.operator_zone.polygon ?? [],
            },
          ]
        : [],
  }

  function renderFeedback(): ReactElement | null {
    if (!feedback) {
      return null
    }
    return <div className={`notice-banner ${feedback.tone}`}>{feedback.message}</div>
  }

  function renderWelcomeStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <div className="wizard-callout">
          <h3>Before you start</h3>
          <ul className="wizard-checklist">
            <li>Camera is mounted and aimed at the output area.</li>
            <li>Camera and mini PC are on the same network.</li>
            <li>You can run the line normally for calibration when you reach the last step.</li>
          </ul>
        </div>
        <div className="wizard-callout">
          <h3>How this setup works</h3>
          <p>
            The backend stays in charge of video, counting, calibration, and alarms. This wizard only saves the setup
            data the backend already understands.
          </p>
        </div>
      </div>
    )
  }

  function renderMountingStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <div className="mount-grid">
          <div className="mount-card good">
            <div className="eyebrow">Good Example</div>
            <h3>Clear top-down view</h3>
            <ol className="wizard-ordered-list">
              <li>Mount above the line and angle down around 30 to 45 degrees.</li>
              <li>Keep the full width of the belt or conveyor in frame.</li>
              <li>Use even lighting so parts stand out from the background.</li>
            </ol>
          </div>
          <div className="mount-card bad">
            <div className="eyebrow">Bad Example</div>
            <h3>What to avoid</h3>
            <ol className="wizard-ordered-list">
              <li>Side angles that hide parts behind each other.</li>
              <li>Cutting off part of the conveyor.</li>
              <li>Aiming toward windows, shiny lights, or glare.</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  function renderCameraStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        {isDemoSource ? (
          <div className="notice-banner info">
            Demo mode is active. Camera details are optional for this source.
          </div>
        ) : null}
        <div className="form-grid">
          <label className="form-field">
            <span>Camera IP</span>
            <input
              onChange={(event) => setCameraForm((current) => ({ ...current, camera_ip: event.target.value }))}
              placeholder="192.168.1.100"
              type="text"
              value={cameraForm.camera_ip}
            />
          </label>
          <label className="form-field">
            <span>Username</span>
            <input
              onChange={(event) => setCameraForm((current) => ({ ...current, camera_username: event.target.value }))}
              type="text"
              value={cameraForm.camera_username}
            />
          </label>
          <label className="form-field">
            <span>Password</span>
            <input
              onChange={(event) => setCameraForm((current) => ({ ...current, camera_password: event.target.value }))}
              placeholder={config?.camera_password ? 'Enter password again to save changes' : ''}
              type="password"
              value={cameraForm.camera_password}
            />
          </label>
          <label className="form-field">
            <span>Video quality</span>
            <select
              onChange={(event) =>
                setCameraForm((current) => ({
                  ...current,
                  stream_profile: event.target.value as StreamProfile,
                }))
              }
              value={cameraForm.stream_profile}
            >
              <option value="sub">Smoother (recommended)</option>
              <option value="main">Sharper (slower)</option>
            </select>
          </label>
        </div>
        <div className="muted-note">
          Passwords are hidden once saved. Enter the password again whenever you change and save camera settings.
        </div>
        <div className="panel-actions">
          <button className="primary" disabled={busyAction === 'camera-save'} onClick={() => void handleCameraSave()} type="button">
            {busyAction === 'camera-save' ? 'Saving camera...' : 'Save camera settings'}
          </button>
          <button disabled={!completion.camera} onClick={goNext} type="button">
            Next
          </button>
        </div>
      </div>
    )
  }

  function renderTestStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <div className="wizard-callout">
          <h3>Test the video feed</h3>
          <p>Use this before drawing anything. If the backend cannot read video here, the later steps will not work.</p>
        </div>
        <div className="panel-actions">
          <button className="primary" disabled={busyAction === 'camera-test'} onClick={() => void handleTestCamera()} type="button">
            {busyAction === 'camera-test' ? 'Testing camera...' : 'Test camera'}
          </button>
          <button disabled={!cameraTestComplete} onClick={goNext} type="button">
            Next
          </button>
        </div>
        {!cameraTest && cameraTestComplete ? (
          <div className="notice-banner success">
            <strong>Live video is already reaching the backend.</strong>
            <div>You can move on without running a separate camera test again.</div>
          </div>
        ) : null}
        {cameraTest ? (
          <div className={`notice-banner ${cameraTest.ok ? 'success' : 'error'}`}>
            <strong>{cameraTest.message}</strong>
            {cameraTest.action_hint ? <div>{cameraTest.action_hint}</div> : null}
          </div>
        ) : null}
        <div className="help-card">
          <div className="eyebrow">Help Finding Camera</div>
          <p>Check the camera app or your router list for the camera address, then confirm video streaming is enabled.</p>
        </div>
      </div>
    )
  }

  function renderRoiStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <SnapshotAnnotator
          draftPoints={roiDraft}
          imageSrc={apiClient.snapshotUrl(snapshotTick)}
          mode="polygon"
          onDraftPointsChange={setRoiDraft}
          onRefresh={() => setSnapshotTick(Date.now())}
          overlays={[...sharedOverlays.roi, ...sharedOverlays.operator]}
          subtitle="Click around the moving parts to outline the output area."
          title="Output Area"
        />
        {roiDraft.length > 0 ? (
          <div className="notice-banner info">
            <strong>Draft only.</strong> Click <strong>Save output area</strong> before the dashboard or backend will use
            this ROI.
          </div>
        ) : completion.roi ? (
          <div className="muted-note">
            The saved output area is already active on the backend. Clearing it will remove the ROI from the dashboard
            and from counting.
          </div>
        ) : (
          <div className="muted-note">
            Keep the ROI around the output accumulation zone only. Objects detected inside this area get counted.
          </div>
        )}
        <div className="panel-actions">
          <button onClick={() => setRoiDraft((points) => points.slice(0, -1))} type="button">
            Undo point
          </button>
          <button disabled={busyAction === 'roi-clear'} onClick={() => void handleClearRoi()} type="button">
            {busyAction === 'roi-clear' ? 'Clearing area...' : completion.roi || roiDraft.length > 0 ? 'Clear saved area' : 'Clear draft'}
          </button>
          <button className="primary" disabled={busyAction === 'roi-save'} onClick={() => void handleSaveRoi()} type="button">
            {busyAction === 'roi-save' ? 'Saving area...' : 'Save output area'}
          </button>
          <button disabled={!completion.roi} onClick={goNext} type="button">
            Next
          </button>
        </div>
      </div>
    )
  }

  function renderOperatorStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <label className="toggle-field">
          <input
            checked={operatorEnabled}
            onChange={(event) => setOperatorEnabled(event.target.checked)}
            type="checkbox"
          />
          <span>Only check for operator when the line slows down.</span>
        </label>
        <SnapshotAnnotator
          draftPoints={operatorDraft}
          imageSrc={apiClient.snapshotUrl(snapshotTick)}
          mode="polygon"
          onDraftPointsChange={setOperatorDraft}
          onRefresh={() => setSnapshotTick(Date.now())}
          overlays={[...sharedOverlays.roi, ...sharedOverlays.operator]}
          subtitle={
            operatorEnabled
              ? 'Draw the area where an operator should appear during a slowdown.'
              : 'This step is optional. Leave it off if you do not need operator checks.'
          }
          title="Operator Zone"
        />
        {operatorEnabled && operatorDraft.length > 0 ? (
          <div className="notice-banner info">
            <strong>Draft only.</strong> Click <strong>Save operator zone</strong> before the backend will use it during drop
            checks.
          </div>
        ) : (
          <div className="muted-note">
            Leave this off unless you really need operator checks. It only matters during slowdown investigation.
          </div>
        )}
        <div className="panel-actions">
          <button disabled={!operatorEnabled} onClick={() => setOperatorDraft((points) => points.slice(0, -1))} type="button">
            Undo point
          </button>
          <button disabled={busyAction === 'operator-clear'} onClick={() => void handleClearOperatorZone()} type="button">
            {busyAction === 'operator-clear'
              ? 'Clearing zone...'
              : config?.operator_zone.enabled || operatorDraft.length > 0
                ? 'Clear saved zone'
                : 'Clear draft'}
          </button>
          <button className="primary" disabled={busyAction === 'operator-save'} onClick={() => void handleSaveOperatorZone()} type="button">
            {busyAction === 'operator-save'
              ? 'Saving operator zone...'
              : operatorEnabled
                ? 'Save operator zone'
                : 'Skip operator zone'}
          </button>
          <button onClick={goNext} type="button">
            Next
          </button>
        </div>
      </div>
    )
  }

  function renderCalibrationStep(): ReactElement {
    return (
      <div className="wizard-step-body">
        <div className="wizard-callout">
          <h3>Run the line like normal</h3>
          <p>
            Keep parts moving at a normal pace while calibration runs. The backend will set a baseline parts-per-minute
            rate from this run.
          </p>
        </div>
        <div aria-label="Calibration progress" className="progress-shell">
          <div className="progress-fill" style={{ width: `${calibrationProgress}%` }} />
        </div>
        <div className="detail-list">
          <div className="detail-row">
            <span className="detail-label">Calibration progress</span>
            <span className="detail-value">
              {status ? `${status.calibration_progress_pct}% (${status.calibration_elapsed_sec}s / ${status.calibration_target_duration_sec}s)` : '--'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Current backend state</span>
            <span className="detail-value">{status ? <StatusPill state={status.state} /> : '...'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Current parts per minute</span>
            <span className="detail-value">{status ? status.rolling_rate_per_min.toFixed(2) : '--'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Baseline</span>
            <span className="detail-value">
              {status?.baseline_rate_per_min == null ? 'Not set yet' : `${status.baseline_rate_per_min.toFixed(2)} parts/min`}
            </span>
          </div>
        </div>
        <SnapshotAnnotator
          draftPoints={[]}
          imageSrc={calibrationSnapshotUrl}
          mode="polygon"
          onDraftPointsChange={() => undefined}
          onRefresh={() => setSnapshotTick(Date.now())}
          overlays={[...sharedOverlays.roi, ...sharedOverlays.operator]}
          subtitle="Snapshot preview refreshes while calibration is running and shows backend-detected objects in green."
          title="Calibration Preview"
        />
        <div className="panel-actions">
          <button
            className="primary"
            disabled={busyAction === 'calibration-start'}
            onClick={() => void handleStartCalibration()}
            type="button"
          >
            {busyAction === 'calibration-start' ? 'Starting calibration...' : 'Start calibrating'}
          </button>
          <button
            disabled={busyAction === 'calibration-reset'}
            onClick={() => void handleResetCalibration()}
            type="button"
          >
            {busyAction === 'calibration-reset' ? 'Resetting baseline...' : 'Recalibrate'}
          </button>
          <button
            disabled={status?.baseline_rate_per_min == null || busyAction === 'monitor-start'}
            onClick={() => void handleStartMonitoring()}
            type="button"
          >
            {busyAction === 'monitor-start' ? 'Starting monitoring...' : 'Start monitoring'}
          </button>
        </div>
      </div>
    )
  }

  function renderCurrentStep(): ReactElement {
    switch (currentStep) {
      case 'welcome':
        return renderWelcomeStep()
      case 'mounting':
        return renderMountingStep()
      case 'camera':
        return renderCameraStep()
      case 'test':
        return renderTestStep()
      case 'roi':
        return renderRoiStep()
      case 'operator':
        return renderOperatorStep()
      case 'calibration':
        return renderCalibrationStep()
      default:
        return renderWelcomeStep()
    }
  }

  return (
    <section className="page-grid">
      <div className="hero-panel">
        <div className="hero-grid">
          <div className="status-strip">
            <div className="eyebrow">Phase 4 Wizard</div>
            <h1 className="hero-title">Setup now lives in React, not in templates.</h1>
            <p className="hero-copy">
              This wizard saves camera settings, drawings, and calibration actions through the stable FastAPI contract.
            </p>
            <div className="hero-actions">
              <button className="primary" onClick={() => setSnapshotTick(Date.now())} type="button">
                Refresh snapshot
              </button>
              <a className="button-link" href="/dashboard">
                Open dashboard
              </a>
            </div>
            {renderFeedback()}
          </div>
          <div className="status-card page-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Backend Status</h2>
                <p className="panel-copy">The wizard never bypasses FastAPI state or saved config.</p>
              </div>
            </div>
            <div className="detail-list">
              <div className="detail-row">
                <span className="detail-label">Current state</span>
                <span className="detail-value">{status ? <StatusPill state={status.state} /> : '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Source</span>
                <span className="detail-value">{diagnostics?.source_kind ?? '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Guidance</span>
                <span className="detail-value wizard-guidance">{stepStateHelp}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="wizard-layout">
        <aside className="page-panel wizard-sidebar">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Step Progress</h2>
              <p className="panel-copy">Move forward in order, or return to any completed step safely.</p>
            </div>
          </div>
          <div className="wizard-step-list">
            {wizardSteps.map((step, index) => (
              <button
                className={`wizard-step-link${step.id === currentStep ? ' active' : ''}`}
                disabled={!isStepAvailable(index)}
                key={step.id}
                onClick={() => goToStep(step.id)}
                type="button"
              >
                <span className="wizard-step-meta">
                  <span className="metric-label">{step.eyebrow}</span>
                  <span className="wizard-step-status">{completion[step.id] ? 'Saved' : 'Needs action'}</span>
                </span>
                <span className="wizard-step-title">{step.title}</span>
                <span className="wizard-step-copy">{step.description}</span>
              </button>
            ))}
          </div>
        </aside>

        <div className="page-panel wizard-main">
          <div className="panel-header">
            <div>
              <div className="eyebrow">{wizardSteps[currentStepIndex]?.eyebrow}</div>
              <h2 className="panel-title">{wizardSteps[currentStepIndex]?.title}</h2>
              <p className="panel-copy">{wizardSteps[currentStepIndex]?.description}</p>
            </div>
            <div className="inline-actions">
              <button disabled={currentStepIndex === 0} onClick={goBack} type="button">
                Back
              </button>
              <button disabled={currentStepIndex >= wizardSteps.length - 1 || !canAdvanceCurrentStep} onClick={goNext} type="button">
                Next
              </button>
            </div>
          </div>
          {renderCurrentStep()}
        </div>

        <aside className="page-panel wizard-sidebar">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Saved Setup</h2>
              <p className="panel-copy">What the backend currently has saved.</p>
            </div>
          </div>
          <div className="detail-list">
            <div className="detail-row">
              <span className="detail-label">Camera</span>
              <span className="detail-value">{completion.camera ? 'Saved' : isDemoSource ? 'Demo mode' : 'Missing'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Camera tested</span>
              <span className="detail-value">{completion.test ? 'Passed' : 'Not yet'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Output area</span>
              <span className="detail-value">{completion.roi ? `${config?.roi_polygon?.length ?? 0} points` : 'Missing'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Operator zone</span>
              <span className="detail-value">{config?.operator_zone.enabled ? 'Enabled' : 'Skipped'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Baseline</span>
              <span className="detail-value">
                {status?.baseline_rate_per_min == null ? 'Not set' : `${status.baseline_rate_per_min.toFixed(2)} parts/min`}
              </span>
            </div>
          </div>
          <div className="panel-actions">
            <button
              className="primary"
              disabled={busyAction === 'geometry-clear-all'}
              onClick={() => void handleClearAllGeometry()}
              type="button"
            >
              {busyAction === 'geometry-clear-all' ? 'Clearing everything...' : 'Clear all setup geometry'}
            </button>
            <button
              disabled={!completion.roi || busyAction === 'roi-clear' || busyAction === 'geometry-clear-all'}
              onClick={() => void handleClearRoi()}
              type="button"
            >
              {busyAction === 'roi-clear' ? 'Clearing ROI...' : 'Clear output area'}
            </button>
            <button
              disabled={!config?.operator_zone.enabled || busyAction === 'operator-clear' || busyAction === 'geometry-clear-all'}
              onClick={() => void handleClearOperatorZone()}
              type="button"
            >
              {busyAction === 'operator-clear' ? 'Clearing zone...' : 'Clear operator zone'}
            </button>
          </div>
          <div className="muted-note">
            These buttons remove the saved backend drawings immediately, even if you are on a different wizard step.
          </div>
        </aside>
      </div>
    </section>
  )
}
