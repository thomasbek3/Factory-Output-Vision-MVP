import { useDeferredValue } from 'react'

import { apiClient } from '../../shared/api/client.ts'
import { EventFeed } from '../../shared/components/EventFeed.tsx'
import { LiveSnapshotPanel } from '../../shared/components/LiveSnapshotPanel.tsx'
import { buildSavedGeometryOverlays } from '../../shared/liveOverlays.ts'
import { countingGuidance } from '../../shared/status.ts'
import { DashboardStatusHeader } from './components/DashboardStatusHeader.tsx'
import { useDashboardData } from './useDashboardData.ts'

export function DashboardPage() {
  const {
    adjustCount,
    busyAction,
    config,
    diagnostics,
    events,
    initialLoadComplete,
    notice,
    refreshSnapshot,
    startMonitoring,
    status,
    stopMonitoring,
    triggerRecalibration,
    videoTick,
    websocketConnected,
  } = useDashboardData()

  const deferredEvents = useDeferredValue(events)
  const countingHints = countingGuidance(config, status, diagnostics)
  const liveOverlays = diagnostics?.source_kind === 'demo' ? buildSavedGeometryOverlays(config) : []
  const liveMedia =
    diagnostics?.source_kind === 'demo'
      ? {
          kind: 'video' as const,
          src: apiClient.activeDemoVideoUrl(videoTick),
          playbackRate: diagnostics.demo_playback_speed,
        }
      : {
          kind: 'image' as const,
          src: apiClient.liveStreamUrl(videoTick),
        }

  return (
    <>
      <DashboardStatusHeader
        busyAction={busyAction}
        diagnostics={diagnostics}
        onRecalibrate={() => void triggerRecalibration()}
        onStartMonitoring={() => void startMonitoring()}
        onStopMonitoring={() => void stopMonitoring()}
        status={status}
        websocketConnected={websocketConnected}
      />

      {notice ? <div className={`notice-banner ${notice.tone}`}>{notice.message}</div> : null}

      <section className="content-grid">
        <div className="content-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Live Metrics</h2>
              <p className="panel-copy">Counts stream over WebSocket. Diagnostics and events resync in the background.</p>
            </div>
            <div className="muted-note">{initialLoadComplete ? 'Live from FastAPI' : 'Loading dashboard...'}</div>
          </div>
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">Parts This Minute</div>
              <div className="metric-value">{status?.counts_this_minute ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Runtime Total</div>
              <div className="metric-value">{status?.runtime_total ?? status?.counts_this_hour ?? '--'}</div>
              <div className="metric-adjust-actions">
                <button
                  className="adjust-button"
                  disabled={busyAction != null}
                  onClick={() => void adjustCount(-1)}
                  title="Remove 1 from count"
                  type="button"
                >
                  &minus;1
                </button>
                <button
                  className="adjust-button"
                  disabled={busyAction != null}
                  onClick={() => void adjustCount(1)}
                  title="Add 1 to count"
                  type="button"
                >
                  +1
                </button>
              </div>
              <div className="metric-subvalue">Operational total for the active hour.</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Proof-Backed</div>
              <div className="metric-value">{status?.proof_backed_total ?? '--'}</div>
              <div className="metric-subvalue">Counts with source-token-backed proof lineage.</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Runtime-Inferred</div>
              <div className="metric-value">{status?.runtime_inferred_only ?? '--'}</div>
              <div className="metric-subvalue">Synthetic approved-chain counts without fresh proof receipts.</div>
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
              <div className="metric-label">Frame Age</div>
              <div className="metric-value">{status?.last_frame_age_sec == null ? '--' : `${status.last_frame_age_sec}s`}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Uptime</div>
              <div className="metric-value">{diagnostics ? `${Math.round(diagnostics.uptime_sec)}s` : '--'}</div>
              <div className="metric-subvalue">Reader alive: {diagnostics?.reader_alive ? 'yes' : 'no'}</div>
            </div>
          </div>
          {countingHints.length > 0 ? (
            <div className="wizard-callout">
              <h3>Counting Checks</h3>
              <ul className="wizard-checklist">
                {countingHints.map((hint) => (
                  <li key={hint}>{hint}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <LiveSnapshotPanel
          frameAgeSec={status?.last_frame_age_sec}
          media={liveMedia}
          onRefresh={refreshSnapshot}
          overlays={liveOverlays}
          refreshLabel={diagnostics?.source_kind === 'demo' ? 'Reload preview' : 'Reload stream'}
          subtitle={
            diagnostics?.source_kind === 'demo'
              ? 'Browser preview plays the active demo video directly for smoother review. Counting state still comes from FastAPI.'
              : 'Camera live view now streams as MJPEG for true motion while counts and diagnostics still come from FastAPI.'
          }
          title="Live View"
        />
      </section>

      <section className="content-grid dashboard-lower-grid">
        <div className="content-panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Operator Controls</h2>
              <p className="panel-copy">Main actions stay visible even while the live view and metrics keep updating.</p>
            </div>
          </div>
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">Source Kind</div>
              <div className="metric-value metric-value-medium">
                {diagnostics?.source_kind === 'demo' ? 'Demo Video' : 'Camera'}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Reconnect Attempts</div>
              <div className="metric-value">{status?.reconnect_attempts_total ?? '--'}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Vision Loop</div>
              <div className="metric-value metric-value-medium">
                {diagnostics?.vision_loop_alive ? 'Alive' : 'Down'}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Latest Error</div>
              <div className="metric-value metric-value-small">{diagnostics?.latest_error_code ?? 'None'}</div>
            </div>
          </div>
          <div className="hero-actions dashboard-secondary-actions">
            <a className="button-link" href="/app/troubleshooting">
              Open troubleshooting
            </a>
            <a className="button-link" href="/wizard">
              Open setup wizard
            </a>
          </div>
        </div>

        <EventFeed
          events={deferredEvents}
          subtitle="Latest state changes and operator-relevant timeline items."
          title="Recent Events"
        />
      </section>
    </>
  )
}
