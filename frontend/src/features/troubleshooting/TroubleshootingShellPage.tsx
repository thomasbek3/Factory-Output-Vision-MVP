import { useState } from 'react'
import type { LineDirection, Point } from '../../shared/api/types.ts'

import { apiClient } from '../../shared/api/client.ts'
import { EventFeed } from '../../shared/components/EventFeed.tsx'
import { LiveSnapshotPanel } from '../../shared/components/LiveSnapshotPanel.tsx'
import { buildSavedGeometryOverlays } from '../../shared/liveOverlays.ts'
import { StatusPill } from '../../shared/components/StatusPill.tsx'
import { countingGuidance, lineDirectionLabel, statusGuidance, statusLabel, statusNextSteps, statusTone } from '../../shared/status.ts'
import { useTroubleshootingData } from './useTroubleshootingData.ts'

type TroubleshootingSnapshotView = 'live' | 'roi' | 'mask' | 'tracks' | 'people'
type GeometryEditMode = 'roi' | 'line' | null

const lineDirectionOptions: Array<{ value: LineDirection; label: string }> = [
  { value: 'both', label: 'Count either direction' },
  { value: 'left_to_right', label: 'Count only left to right' },
  { value: 'right_to_left', label: 'Count only right to left' },
  { value: 'top_to_bottom', label: 'Count only top to bottom' },
  { value: 'bottom_to_top', label: 'Count only bottom to top' },
  { value: 'p1_to_p2', label: 'Count only start point to end point' },
  { value: 'p2_to_p1', label: 'Count only end point to start point' },
]

const snapshotViewCopy: Record<TroubleshootingSnapshotView, { label: string; subtitle: string }> = {
  live: {
    label: 'Live view',
    subtitle: 'Use this to confirm the camera still sees the line and drawings.',
  },
  roi: {
    label: 'ROI view',
    subtitle: 'Shows only the masked counting area from the live worker cache.',
  },
  mask: {
    label: 'Mask view',
    subtitle: 'Shows the foreground mask and detected blobs from the worker cache.',
  },
  tracks: {
    label: 'Tracks view',
    subtitle: 'Shows the live frame with backend detection boxes and track labels.',
  },
  people: {
    label: 'People view',
    subtitle: 'Shows ignored people in magenta so you can verify what the mask is blocking out.',
  },
}

function cameraConnectionLabel(currentState: string | undefined, readerAlive: boolean | undefined): string {
  if (currentState === 'RUNNING_YELLOW_RECONNECTING') {
    return 'Reconnecting'
  }
  if (readerAlive) {
    return 'Connected'
  }
  return 'Waiting for video'
}

export function TroubleshootingShellPage() {
  const [snapshotView, setSnapshotView] = useState<TroubleshootingSnapshotView>('live')
  const [geometryEditMode, setGeometryEditMode] = useState<GeometryEditMode>(null)
  const [geometryError, setGeometryError] = useState<string | null>(null)
  const [roiDraft, setRoiDraft] = useState<Point[]>([])
  const [lineDraft, setLineDraft] = useState<Point[]>([])
  const [lineDirection, setLineDirection] = useState<LineDirection>('both')
  const [selectedUpload, setSelectedUpload] = useState<File | null>(null)
  const {
    busyAction,
    clearLine,
    clearRoi,
    config,
    demoVideos,
    diagnostics,
    events,
    notice,
    refresh,
    refreshSnapshot,
    resetCalibration,
    resetCounts,
    restartVideo,
    saveLine,
    saveRoi,
    selectDemoVideo,
    setDemoPlaybackSpeed,
    setPersonIgnore,
    snapshotTick,
    status,
    uploadDemoVideo,
    videoTick,
  } = useTroubleshootingData()

  const currentState = status?.state ?? diagnostics?.current_state ?? 'UNKNOWN'
  const nextSteps = statusNextSteps(currentState)
  const tone = statusTone(currentState)
  const lastErrorMessage = diagnostics?.latest_error_message ?? 'No recent backend error message.'
  const countingHints = countingGuidance(config, status, diagnostics)
  const liveOverlays =
    snapshotView === 'live'
      ? buildSavedGeometryOverlays(config).filter((overlay) => {
          if (geometryEditMode === 'roi' && overlay.label === 'Saved output area') {
            return false
          }
          if (geometryEditMode === 'line' && overlay.label === 'Saved count line') {
            return false
          }
          return true
        })
      : []
  const liveMedia =
    snapshotView === 'live' && diagnostics?.source_kind === 'demo'
      ? {
          kind: 'video' as const,
          fallbackImageSrc: apiClient.liveStreamUrl(videoTick),
          src: apiClient.activeDemoVideoUrl(videoTick),
          playbackRate: diagnostics.demo_playback_speed,
          showNativeControls: geometryEditMode == null,
        }
      : snapshotView === 'live'
        ? {
            kind: 'image' as const,
            src: apiClient.liveStreamUrl(videoTick),
          }
      : {
          kind: 'image' as const,
          src: apiClient.debugSnapshotUrl(snapshotTick, snapshotView),
        }
  const playbackSpeed = diagnostics?.demo_playback_speed ?? 1
  const personIgnoreEnabled = diagnostics?.person_ignore_enabled ?? false
  const currentDemoVideoName = diagnostics?.demo_video_name ?? 'No demo selected'
  const currentDraft = geometryEditMode === 'roi' ? roiDraft : lineDraft
  const geometrySaveAction = geometryEditMode === 'roi' ? 'roi-save' : geometryEditMode === 'line' ? 'line-save' : null
  const geometryClearAction = geometryEditMode === 'roi' ? 'roi-clear' : geometryEditMode === 'line' ? 'line-clear' : null
  const geometrySaveBusy = geometrySaveAction != null && busyAction === geometrySaveAction
  const geometryClearBusy = geometryClearAction != null && busyAction === geometryClearAction
  const geometryHint =
    geometryEditMode === 'roi'
      ? roiDraft.length === 0
        ? 'Click each corner of the output area. Save after at least three points.'
        : `${roiDraft.length} draft point${roiDraft.length === 1 ? '' : 's'} placed. Click to add more points.`
      : geometryEditMode === 'line'
        ? lineDraft.length === 0
          ? 'Click the first point of the count line.'
          : lineDraft.length === 1
            ? 'Click the second point of the count line.'
            : 'Draft line ready. Click again to restart it, or save this one.'
        : undefined
  const savedGeometrySummary =
    geometryEditMode === 'roi'
      ? config?.roi_polygon?.length
        ? `${config.roi_polygon.length} saved points`
        : 'Missing'
      : geometryEditMode === 'line'
        ? config?.line
          ? lineDirectionLabel(config.line.direction)
          : 'Missing'
        : null

  function cancelGeometryEdit(): void {
    setGeometryEditMode(null)
    setGeometryError(null)
    setRoiDraft([])
    setLineDraft([])
  }

  function handleRoiDraftChange(points: Point[]): void {
    setGeometryError(null)
    setRoiDraft(points)
  }

  function handleLineDraftChange(points: Point[]): void {
    setGeometryError(null)
    setLineDraft(points)
  }

  function handleViewChange(view: TroubleshootingSnapshotView): void {
    if (view !== 'live') {
      cancelGeometryEdit()
    }
    setSnapshotView(view)
  }

  function startRoiEdit(): void {
    setSnapshotView('live')
    setGeometryEditMode('roi')
    setGeometryError(null)
    setRoiDraft(config?.roi_polygon ?? [])
  }

  function startLineEdit(): void {
    setSnapshotView('live')
    setGeometryEditMode('line')
    setGeometryError(null)
    setLineDraft(config?.line ? [config.line.p1, config.line.p2] : [])
    setLineDirection(config?.line?.direction ?? 'both')
  }

  async function handleSaveGeometry(): Promise<void> {
    if (geometryEditMode === 'roi') {
      if (roiDraft.length < 3) {
        setGeometryError('Click at least three points to save the output area.')
        return
      }
      setGeometryError(null)
      const saved = await saveRoi(roiDraft)
      if (saved) {
        cancelGeometryEdit()
      }
      return
    }

    if (geometryEditMode === 'line') {
      if (lineDraft.length !== 2) {
        setGeometryError('Click exactly two points to save the count line.')
        return
      }
      setGeometryError(null)
      const saved = await saveLine(lineDraft[0], lineDraft[1], lineDirection)
      if (saved) {
        cancelGeometryEdit()
      }
    }
  }

  async function handleClearSavedGeometry(): Promise<void> {
    if (geometryEditMode === 'roi') {
      const cleared = await clearRoi()
      if (cleared) {
        cancelGeometryEdit()
      }
      return
    }

    if (geometryEditMode === 'line') {
      const cleared = await clearLine()
      if (cleared) {
        cancelGeometryEdit()
      }
    }
  }

  function handleUndoGeometryPoint(): void {
    if (geometryEditMode === 'roi') {
      setRoiDraft((points) => points.slice(0, -1))
      return
    }
    if (geometryEditMode === 'line') {
      setLineDraft((points) => points.slice(0, -1))
    }
  }

  function handleClearDraft(): void {
    if (geometryEditMode === 'roi') {
      setRoiDraft([])
      return
    }
    if (geometryEditMode === 'line') {
      setLineDraft([])
    }
  }

  return (
    <section className="page-grid">
      <div className="hero-panel">
        <div className="dashboard-hero-grid">
          <div className="dashboard-status-panel">
            <div className={`status-beacon ${tone}`} />
            <div className="status-strip">
              <div className="eyebrow">Phase 6 Troubleshooting</div>
              <h1 className="hero-title">{statusLabel(currentState)}</h1>
              <p className="hero-copy">{statusGuidance(currentState)}</p>
              <div className="troubleshooting-guidance-grid">
                <div className="wizard-callout">
                  <h3>What&apos;s happening</h3>
                  <p>{lastErrorMessage}</p>
                </div>
                <div className="wizard-callout">
                  <h3>What to do next</h3>
                  <ol className="wizard-ordered-list">
                    {nextSteps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </div>
              </div>
              <div className="hero-actions">
                <button
                  className="primary"
                  disabled={busyAction === 'restart-video'}
                  onClick={() => void restartVideo()}
                  type="button"
                >
                  {busyAction === 'restart-video' ? 'Restarting video...' : 'Restart video connection'}
                </button>
                <button
                  disabled={busyAction === 'reset-calibration'}
                  onClick={() => void resetCalibration()}
                  type="button"
                >
                  {busyAction === 'reset-calibration' ? 'Resetting calibration...' : 'Reset calibration'}
                </button>
                <button
                  disabled={busyAction === 'reset-counts'}
                  onClick={() => void resetCounts()}
                  type="button"
                >
                  {busyAction === 'reset-counts' ? 'Resetting counts...' : 'Reset counts'}
                </button>
                <a className="button-link" href={apiClient.supportBundleUrl()}>
                  Download support bundle
                </a>
                <button onClick={() => void refresh()} type="button">
                  Refresh diagnostics
                </button>
              </div>
              {notice ? <div className={`notice-banner ${notice.tone}`}>{notice.message}</div> : null}
            </div>
          </div>

          <div className="status-card page-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Current Status</h2>
                <p className="panel-copy">Backend health and operator-facing state at a glance.</p>
              </div>
            </div>
            <div className="detail-list">
              <div className="detail-row">
                <span className="detail-label">Current state</span>
                <span className="detail-value">{status ? <StatusPill state={status.state} /> : '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Camera status</span>
                <span className="detail-value">
                  {cameraConnectionLabel(currentState, diagnostics?.reader_alive)}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Reconnect attempts</span>
                <span className="detail-value">{diagnostics?.reconnect_attempts_total ?? '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Last frame received</span>
                <span className="detail-value">
                  {diagnostics?.last_frame_age_sec == null ? 'Waiting for video' : `${diagnostics.last_frame_age_sec}s ago`}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">People detected</span>
                <span className="detail-value">{diagnostics?.people_detected_count ?? 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="content-grid">
        <div className="content-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Camera Health</h2>
              <p className="panel-copy">Use this to confirm whether the camera and worker loops are alive.</p>
            </div>
          </div>
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">Camera Status</div>
              <div className="metric-value metric-value-medium">
                {cameraConnectionLabel(currentState, diagnostics?.reader_alive)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Source Kind</div>
              <div className="metric-value metric-value-medium">
                {diagnostics?.source_kind === 'demo' ? 'Demo Video' : 'Camera'}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Reader Loop</div>
              <div className="metric-value metric-value-medium">{diagnostics?.reader_alive ? 'Alive' : 'Down'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Vision Loop</div>
              <div className="metric-value metric-value-medium">
                {diagnostics?.vision_loop_alive ? 'Alive' : 'Down'}
              </div>
            </div>
          </div>
        </div>

        <div className="troubleshooting-stack">
          <LiveSnapshotPanel
            controls={
              <>
                {(['live', 'roi', 'mask', 'tracks', 'people'] as TroubleshootingSnapshotView[]).map((view) => (
                  <button
                    className={snapshotView === view ? 'primary' : undefined}
                    key={view}
                    onClick={() => handleViewChange(view)}
                    type="button"
                  >
                    {snapshotViewCopy[view].label}
                  </button>
                ))}
                {snapshotView === 'live' ? (
                  <>
                    <button
                      className={geometryEditMode === 'roi' ? 'primary' : undefined}
                      onClick={startRoiEdit}
                      type="button"
                    >
                      {geometryEditMode === 'roi' ? 'Editing output area' : 'Edit output area'}
                    </button>
                    <button
                      className={geometryEditMode === 'line' ? 'primary' : undefined}
                      onClick={startLineEdit}
                      type="button"
                    >
                      {geometryEditMode === 'line' ? 'Editing count line' : 'Edit count line'}
                    </button>
                  </>
                ) : null}
              </>
            }
            editor={
              geometryEditMode === 'roi'
                ? {
                    draftPoints: currentDraft,
                    hint: geometryHint,
                    mode: 'polygon' as const,
                    onDraftPointsChange: handleRoiDraftChange,
                  }
                : geometryEditMode === 'line'
                  ? {
                      draftPoints: currentDraft,
                      hint: geometryHint,
                      mode: 'line' as const,
                      onDraftPointsChange: handleLineDraftChange,
                    }
                  : undefined
            }
            frameAgeSec={diagnostics?.last_frame_age_sec}
            media={liveMedia}
            onRefresh={refreshSnapshot}
            overlays={liveOverlays}
            refreshLabel={liveMedia.kind === 'video' ? 'Reload preview' : snapshotView === 'live' ? 'Reload stream' : 'Refresh snapshot'}
            subtitle={
              liveMedia.kind === 'video'
                ? 'Browser preview plays the active demo file directly so you can scrub and inspect real motion. Debug views still come from the backend worker.'
                : snapshotView === 'live'
                  ? 'Camera live view now streams as MJPEG for true motion. ROI, mask, tracks, and people remain backend debug snapshots.'
                  : snapshotViewCopy[snapshotView].subtitle
            }
            title="Camera And Debug Views"
          />

          {geometryEditMode ? (
            <div className="page-panel geometry-editor-panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">
                    {geometryEditMode === 'roi' ? 'Edit Output Area' : 'Edit Count Line'}
                  </h2>
                  <p className="panel-copy">
                    {geometryEditMode === 'roi'
                      ? 'Click directly on the live view to trace the counting area. The draft stays on screen until you save or cancel.'
                      : 'Click two points directly on the live view to place the count line, then choose which crossing direction should count.'}
                  </p>
                </div>
              </div>

              {geometryError ? <div className="notice-banner error">{geometryError}</div> : null}

              <div className="detail-list compact-detail-list">
                <div className="detail-row">
                  <span className="detail-label">Draft status</span>
                  <span className="detail-value">
                    {geometryEditMode === 'roi'
                      ? `${currentDraft.length} point${currentDraft.length === 1 ? '' : 's'}`
                      : `${currentDraft.length}/2 points`}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Saved geometry</span>
                  <span className="detail-value">{savedGeometrySummary}</span>
                </div>
              </div>

              {geometryEditMode === 'line' ? (
                <label className="form-field compact">
                  <span>Count direction</span>
                  <select
                    onChange={(event) => setLineDirection(event.target.value as LineDirection)}
                    value={lineDirection}
                  >
                    {lineDirectionOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <div className="hero-actions dashboard-secondary-actions">
                <button
                  disabled={currentDraft.length === 0 || geometrySaveBusy || geometryClearBusy}
                  onClick={handleUndoGeometryPoint}
                  type="button"
                >
                  Undo point
                </button>
                <button
                  disabled={currentDraft.length === 0 || geometrySaveBusy || geometryClearBusy}
                  onClick={handleClearDraft}
                  type="button"
                >
                  Clear draft
                </button>
                <button
                  className="primary"
                  disabled={
                    geometrySaveBusy ||
                    geometryClearBusy ||
                    (geometryEditMode === 'roi' ? currentDraft.length < 3 : currentDraft.length !== 2)
                  }
                  onClick={() => void handleSaveGeometry()}
                  type="button"
                >
                  {geometrySaveBusy
                    ? geometryEditMode === 'roi'
                      ? 'Saving area...'
                      : 'Saving line...'
                    : geometryEditMode === 'roi'
                      ? 'Save output area'
                      : 'Save count line'}
                </button>
                <button
                  disabled={
                    geometrySaveBusy ||
                    geometryClearBusy ||
                    (geometryEditMode === 'roi' ? !config?.roi_polygon?.length : !config?.line)
                  }
                  onClick={() => void handleClearSavedGeometry()}
                  type="button"
                >
                  {geometryClearBusy
                    ? geometryEditMode === 'roi'
                      ? 'Clearing area...'
                      : 'Clearing line...'
                    : geometryEditMode === 'roi'
                      ? 'Clear saved area'
                      : 'Clear saved line'}
                </button>
                <button disabled={geometrySaveBusy || geometryClearBusy} onClick={cancelGeometryEdit} type="button">
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="content-grid troubleshooting-lower-grid">
        <div className="content-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Counting And Recovery</h2>
              <p className="panel-copy">These values help confirm whether the counter or baseline needs attention.</p>
            </div>
          </div>
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">Parts This Minute</div>
              <div className="metric-value">{status?.counts_this_minute ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Runtime Total</div>
              <div className="metric-value">{status?.runtime_total ?? status?.counts_this_hour ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Proof-Backed</div>
              <div className="metric-value">{status?.proof_backed_total ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Runtime-Inferred</div>
              <div className="metric-value">{status?.runtime_inferred_only ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Baseline Parts/Min</div>
              <div className="metric-value">
                {status?.baseline_rate_per_min == null ? '--' : status.baseline_rate_per_min.toFixed(2)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Current Rolling Rate</div>
              <div className="metric-value">{status ? status.rolling_rate_per_min.toFixed(2) : '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Latest Error Code</div>
              <div className="metric-value metric-value-small">{diagnostics?.latest_error_code ?? 'None'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Operator Check</div>
              <div className="metric-value metric-value-medium">{status?.operator_absent ? 'Absent' : 'Clear'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Count Direction</div>
              <div className="metric-value metric-value-small">
                {config?.line ? lineDirectionLabel(config.line.direction) : 'Missing'}
              </div>
            </div>
          </div>
          {countingHints.length > 0 ? (
            <div className="wizard-callout">
              <h3>Why Counts May Stay At Zero</h3>
              <ul className="wizard-checklist">
                {countingHints.map((hint) => (
                  <li key={hint}>{hint}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="page-grid troubleshooting-stack">
          {diagnostics?.source_kind === 'demo' ? (
            <div className="page-panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Demo Playback Lab</h2>
                  <p className="panel-copy">Restart the demo from frame 1, change playback speed, and test whether person masking helps.</p>
                </div>
              </div>
              <div className="detail-list">
                <div className="detail-row">
                  <span className="detail-label">Current playback speed</span>
                  <span className="detail-value">{playbackSpeed.toFixed(2)}x</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Active demo video</span>
                  <span className="detail-value">{currentDemoVideoName}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Person ignore mask</span>
                  <span className="detail-value">{personIgnoreEnabled ? 'Enabled' : 'Disabled'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">People detected now</span>
                  <span className="detail-value">{diagnostics?.people_detected_count ?? 0}</span>
                </div>
              </div>
              <div className="hero-actions dashboard-secondary-actions">
                <button
                  className="primary"
                  disabled={busyAction === 'restart-video'}
                  onClick={() => void restartVideo()}
                  type="button"
                >
                  {busyAction === 'restart-video' ? 'Restarting demo...' : 'Restart demo from beginning'}
                </button>
                {[0.5, 1, 2, 4].map((speed) => (
                  <button
                    className={Math.abs(playbackSpeed - speed) < 0.01 ? 'primary' : undefined}
                    disabled={busyAction === `playback-speed-${speed}`}
                    key={speed}
                    onClick={() => void setDemoPlaybackSpeed(speed)}
                    type="button"
                  >
                    {busyAction === `playback-speed-${speed}` ? `Setting ${speed}x...` : `${speed}x playback`}
                  </button>
                ))}
                <button
                  className={personIgnoreEnabled ? 'primary' : undefined}
                  disabled={busyAction === 'enable-person-ignore' || busyAction === 'disable-person-ignore'}
                  onClick={() => void setPersonIgnore(!personIgnoreEnabled)}
                  type="button"
                >
                  {busyAction === 'enable-person-ignore' || busyAction === 'disable-person-ignore'
                    ? 'Updating mask...'
                    : personIgnoreEnabled
                      ? 'Disable person ignore'
                      : 'Enable person ignore'}
                </button>
              </div>
              <div className="wizard-callout">
                <h3>Upload a real video</h3>
                <div className="form-field compact">
                  <span>Pick a video file from this machine</span>
                  <input
                    accept=".mp4,.mov,.m4v,.avi,.mkv,.webm,.mjpg,.mjpeg"
                    onChange={(event) => setSelectedUpload(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                </div>
                <div className="muted-note">
                  Uploads are converted into a browser-safe demo MP4 automatically so the preview plays as real motion.
                </div>
                <div className="hero-actions dashboard-secondary-actions">
                  <button
                    className="primary"
                    disabled={!selectedUpload || busyAction === 'upload-demo-video'}
                    onClick={() => void (selectedUpload ? uploadDemoVideo(selectedUpload) : Promise.resolve())}
                    type="button"
                  >
                    {busyAction === 'upload-demo-video' ? 'Uploading video...' : 'Upload and use this video'}
                  </button>
                </div>
              </div>
              <div className="wizard-callout">
                <h3>Available demo videos</h3>
                {demoVideos.length === 0 ? (
                  <p>No uploaded demo videos yet.</p>
                ) : (
                  <ul className="event-list">
                    {demoVideos.map((video) => (
                      <li className="event-item" key={video.path}>
                        <div className="event-meta">{video.selected ? 'Active demo source' : 'Available demo source'}</div>
                        <div><strong>{video.name}</strong></div>
                        <div className="muted-note">
                          {Math.max(1, Math.round(video.size_bytes / (1024 * 1024)))} MB
                          {' · '}
                          {video.managed ? 'Uploaded in app' : 'External fallback source'}
                        </div>
                        <div className="hero-actions dashboard-secondary-actions">
                          <button
                            className={video.selected ? 'primary' : undefined}
                            disabled={video.selected || busyAction === 'select-demo-video'}
                            onClick={() => void selectDemoVideo(video.path, video.name)}
                            type="button"
                          >
                            {video.selected ? 'Currently selected' : 'Use this video'}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="wizard-callout">
                <h3>How to use this</h3>
                <ul className="wizard-checklist">
                  <li>Restart the demo after changing ROI or line so your test always starts from the same point.</li>
                  <li>Use 2x or 4x playback to get more count events through the same footage faster.</li>
                  <li>Enable person ignore to black out detected people before motion counting. It helps only when the product is still at least partly visible.</li>
                  <li>Use People view to confirm the backend is actually tracking the operator in magenta before trusting the mask.</li>
                  <li>Uploading a new demo video selects it immediately and uses it for the next restart/test cycle.</li>
                </ul>
              </div>
            </div>
          ) : null}

          <div className="page-panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Support</h2>
                <p className="panel-copy">Bundle the current diagnostics, logs, and database for support review.</p>
              </div>
            </div>
            <div className="detail-list">
              <div className="detail-row">
                <span className="detail-label">Database path</span>
                <span className="detail-value">{diagnostics?.db_path ?? '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Log directory</span>
                <span className="detail-value">{diagnostics?.log_directory ?? '...'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Last error message</span>
                <span className="detail-value support-detail-value">{lastErrorMessage}</span>
              </div>
            </div>
            <div className="hero-actions dashboard-secondary-actions">
              <a className="button-link primary" href={apiClient.supportBundleUrl()}>
                Download support bundle
              </a>
              <a className="button-link" href="/dashboard">
                Open dashboard
              </a>
              <a className="button-link" href="/wizard">
                Open setup wizard
              </a>
            </div>
          </div>

          <EventFeed
            emptyMessage="No recent support events."
            events={events}
            subtitle="Recent state changes and errors that help explain what happened."
            title="Recent Events"
          />
        </div>
      </div>
    </section>
  )
}
