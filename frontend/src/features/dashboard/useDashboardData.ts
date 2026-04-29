import { startTransition, useCallback, useEffect, useEffectEvent, useState } from 'react'

import { apiClient } from '../../shared/api/client.ts'
import type { ConfigResponse, DiagnosticsResponse, EventItem, MetricsEvent, MetricsPayload, StatusResponse } from '../../shared/api/types.ts'

const eventLimit = 20

export type DashboardNotice = {
  tone: 'info' | 'success' | 'error'
  message: string
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function metricEventToEventItem(event: MetricsEvent): EventItem {
  return {
    id: null,
    event_type: event.type,
    state_from: event.state_from,
    state_to: event.state_to,
    message: event.message,
    created_at: new Date().toISOString(),
  }
}

function eventKey(event: Pick<EventItem, 'event_type' | 'state_from' | 'state_to' | 'message'>): string {
  return [event.event_type, event.state_from ?? '', event.state_to ?? '', event.message].join('|')
}

function prependEvent(existing: EventItem[], incoming: EventItem): EventItem[] {
  const incomingKey = eventKey(incoming)
  if (existing.some((event) => eventKey(event) === incomingKey)) {
    return existing
  }
  return [incoming, ...existing].slice(0, eventLimit)
}

function statusFromMetricsPayload(payload: MetricsPayload): StatusResponse {
  return {
    state: payload.state,
    count_source: payload.count_source,
    baseline_rate_per_min: payload.baseline_rate_per_min,
    calibration_progress_pct: payload.calibration_progress_pct,
    calibration_elapsed_sec: payload.calibration_elapsed_sec,
    calibration_target_duration_sec: payload.calibration_target_duration_sec,
    rolling_rate_per_min: payload.rolling_rate_per_min,
    counts_this_minute: payload.counts_this_minute,
    counts_this_hour: payload.counts_this_hour,
    runtime_total: payload.runtime_total,
    proof_backed_total: payload.proof_backed_total,
    runtime_inferred_only: payload.runtime_inferred_only,
    last_frame_age_sec: payload.last_frame_age_sec,
    reconnect_attempts_total: payload.reconnect_attempts_total,
    operator_absent: payload.operator_absent,
  }
}

export function useDashboardData() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [notice, setNotice] = useState<DashboardNotice | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [videoTick, setVideoTick] = useState(0)
  const [websocketConnected, setWebsocketConnected] = useState(false)
  const [initialLoadComplete, setInitialLoadComplete] = useState(false)

  const refreshSupportingData = useCallback(async () => {
    const [configResponse, diagnosticsResponse, eventsResponse] = await Promise.all([
      apiClient.getConfig(),
      apiClient.getDiagnostics(),
      apiClient.getEvents(eventLimit),
    ])
    startTransition(() => {
      setConfig(configResponse)
      setDiagnostics(diagnosticsResponse)
      setEvents(eventsResponse.items)
    })
  }, [])

  const applyMetricsPayload = useEffectEvent((payload: MetricsPayload) => {
    startTransition(() => {
      setStatus(statusFromMetricsPayload(payload))
      if (payload.last_event) {
        setEvents((current) => prependEvent(current, metricEventToEventItem(payload.last_event as MetricsEvent)))
      }
    })
  })

  useEffect(() => {
    let active = true

    async function loadInitial(): Promise<void> {
      try {
        const [statusResponse, configResponse, diagnosticsResponse, eventsResponse] = await Promise.all([
          apiClient.getStatus(),
          apiClient.getConfig(),
          apiClient.getDiagnostics(),
          apiClient.getEvents(eventLimit),
        ])

        if (!active) {
          return
        }

        startTransition(() => {
          setStatus(statusResponse)
          setConfig(configResponse)
          setDiagnostics(diagnosticsResponse)
          setEvents(eventsResponse.items)
          setInitialLoadComplete(true)
          setNotice((current) => (current?.tone === 'error' ? current : null))
        })
      } catch (error) {
        if (!active) {
          return
        }
        setNotice({ tone: 'error', message: toMessage(error, 'Unable to load dashboard data.') })
        setInitialLoadComplete(true)
      }
    }

    void loadInitial()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let closed = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null

    const connect = () => {
      socket = new WebSocket(apiClient.metricsWebSocketUrl())

      socket.onopen = () => {
        if (!closed) {
          setWebsocketConnected(true)
        }
      }

      socket.onmessage = (event) => {
        try {
          applyMetricsPayload(JSON.parse(event.data) as MetricsPayload)
        } catch {
          return
        }
      }

      socket.onerror = () => {
        socket?.close()
      }

      socket.onclose = () => {
        if (closed) {
          return
        }
        setWebsocketConnected(false)
        reconnectTimer = window.setTimeout(connect, 1000)
      }
    }

    connect()
    return () => {
      closed = true
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
      }
      socket?.close()
    }
  }, [])

  useEffect(() => {
    let active = true

    const timer = window.setInterval(() => {
      void (async () => {
        try {
          await refreshSupportingData()
        } catch (error) {
          if (!active) {
            return
          }
          setNotice((current) => current ?? { tone: 'error', message: toMessage(error, 'Unable to refresh dashboard details.') })
        }
      })()
    }, 10000)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [refreshSupportingData])

  async function runControlAction(
    action: string,
    operation: () => Promise<StatusResponse>,
    successMessage: string,
  ): Promise<void> {
    setBusyAction(action)
    try {
      const nextStatus = await operation()
      startTransition(() => {
        setStatus(nextStatus)
        setNotice({ tone: 'success', message: successMessage })
      })
      await refreshSupportingData()
      setVideoTick(Date.now())
    } catch (error) {
      setNotice({ tone: 'error', message: toMessage(error, 'Unable to update monitoring state.') })
    } finally {
      setBusyAction(null)
    }
  }

  async function handleStartMonitoring(): Promise<void> {
    await runControlAction('monitor-start', () => apiClient.startMonitoring(), 'Monitoring started.')
  }

  async function handleStopMonitoring(): Promise<void> {
    await runControlAction('monitor-stop', () => apiClient.stopMonitoring(), 'Monitoring stopped.')
  }

  async function handleRecalibrate(): Promise<void> {
    setBusyAction('recalibrate')
    try {
      if (status?.baseline_rate_per_min != null) {
        await apiClient.resetCalibration()
      }
      const nextStatus = await apiClient.startCalibration()
      startTransition(() => {
        setStatus(nextStatus)
        setNotice({
          tone: nextStatus.state === 'CALIBRATING' ? 'success' : 'info',
          message:
            nextStatus.state === 'CALIBRATING'
              ? 'Calibration started. Let the line run normally until the baseline is set.'
              : 'Dashboard requested calibration, but setup is not ready yet.',
        })
      })
      await refreshSupportingData()
      setVideoTick(Date.now())
    } catch (error) {
      setNotice({ tone: 'error', message: toMessage(error, 'Unable to update calibration.') })
    } finally {
      setBusyAction(null)
    }
  }

  async function handleAdjustCount(delta: number): Promise<void> {
    await runControlAction(
      'adjust-count',
      () => apiClient.adjustCount({ delta }),
      delta > 0 ? `Added ${delta} to count.` : `Removed ${Math.abs(delta)} from count.`,
    )
  }

  return {
    adjustCount: handleAdjustCount,
    busyAction,
    config,
    diagnostics,
    events,
    initialLoadComplete,
    notice,
    refreshSnapshot: () => {
      setVideoTick(Date.now())
    },
    videoTick,
    startMonitoring: handleStartMonitoring,
    status,
    stopMonitoring: handleStopMonitoring,
    triggerRecalibration: handleRecalibrate,
    websocketConnected,
  }
}
