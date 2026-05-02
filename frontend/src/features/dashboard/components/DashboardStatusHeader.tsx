import type { DiagnosticsResponse, StatusResponse } from '../../../shared/api/types.ts'
import { StatusPill } from '../../../shared/components/StatusPill.tsx'
import { countSourceLabel, displayStateForContext, statusGuidance, statusLabel, statusTone } from '../../../shared/status.ts'

type DashboardStatusHeaderProps = {
  busyAction: string | null
  diagnostics: DiagnosticsResponse | null
  status: StatusResponse | null
  websocketConnected: boolean
  onRecalibrate: () => void
  onStartMonitoring: () => void
  onStopMonitoring: () => void
}

export function DashboardStatusHeader({
  busyAction,
  diagnostics,
  status,
  websocketConnected,
  onRecalibrate,
  onStartMonitoring,
  onStopMonitoring,
}: DashboardStatusHeaderProps) {
  const state = status?.state ?? diagnostics?.current_state ?? 'UNKNOWN'
  const displayState = displayStateForContext(state, diagnostics)
  const tone = statusTone(displayState)
  const canRecalibrate = Boolean(status)
  const recalibrateLabel = status?.baseline_rate_per_min == null ? 'Start calibration' : 'Recalibrate'
  const sourceLabel =
    diagnostics?.source_kind === 'demo'
      ? `Demo Video${diagnostics.demo_video_name ? `: ${diagnostics.demo_video_name}` : ''}`
      : 'Camera'

  return (
    <section className="hero-panel">
      <div className="dashboard-hero-grid">
        <div className="dashboard-status-panel">
          <div className={`status-beacon ${tone}`} />
          <div className="status-strip">
            <div className="eyebrow">Phase 5 Dashboard</div>
            <h1 className="hero-title">{statusLabel(displayState)}</h1>
            <p className="hero-copy">{statusGuidance(displayState)}</p>
            <div className="tag-row">
              <span className="tag">Counting: {countSourceLabel(status?.count_source ?? 'vision')}</span>
              <span className="tag">Source: {sourceLabel}</span>
              <span className="tag">Live feed: {websocketConnected ? 'Connected' : 'Reconnecting'}</span>
              {status?.operator_absent ? <span className="tag">Operator absent</span> : null}
            </div>
            <div className="hero-actions">
              <button
                className="primary"
                disabled={busyAction === 'monitor-start'}
                onClick={onStartMonitoring}
                type="button"
              >
                {busyAction === 'monitor-start' ? 'Starting monitoring...' : 'Start monitoring'}
              </button>
              <button disabled={busyAction === 'monitor-stop'} onClick={onStopMonitoring} type="button">
                {busyAction === 'monitor-stop' ? 'Stopping monitoring...' : 'Stop monitoring'}
              </button>
              <button disabled={!canRecalibrate || busyAction === 'recalibrate'} onClick={onRecalibrate} type="button">
                {busyAction === 'recalibrate' ? 'Updating baseline...' : recalibrateLabel}
              </button>
            </div>
          </div>
        </div>

        <div className="status-card page-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Backend State</h2>
              <p className="panel-copy">FastAPI remains the source of truth for status and controls.</p>
            </div>
          </div>
          <div className="detail-list">
            <div className="detail-row">
              <span className="detail-label">Current state</span>
              <span className="detail-value">{status ? <StatusPill state={displayState} /> : '...'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Reconnect attempts</span>
              <span className="detail-value">{status?.reconnect_attempts_total ?? '...'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Last frame age</span>
              <span className="detail-value">
                {status?.last_frame_age_sec == null ? '...' : `${status.last_frame_age_sec}s`}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Latest error</span>
              <span className="detail-value">{diagnostics?.latest_error_code ?? 'None'}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
