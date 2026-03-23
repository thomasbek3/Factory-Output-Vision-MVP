import type {
  CameraConfigRequest,
  CameraTestResponse,
  ConfigResponse,
  DemoPlaybackRequest,
  DemoVideoListResponse,
  DemoVideoSelectRequest,
  DiagnosticsResponse,
  EventsResponse,
  LineConfigRequest,
  OkResponse,
  OperatorZoneRequest,
  PersonIgnoreRequest,
  RoiConfigRequest,
  StatusResponse,
} from './types.ts'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const BACKEND_ORIGIN = import.meta.env.VITE_BACKEND_ORIGIN ?? (import.meta.env.DEV ? 'http://127.0.0.1:8080' : '')

async function parseErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with status ${response.status}`
  }
  const text = await response.text()
  return text || `Request failed with status ${response.status}`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response))
  }

  return (await response.json()) as T
}

export const apiClient = {
  getStatus(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/status')
  },
  getConfig(): Promise<ConfigResponse> {
    return requestJson<ConfigResponse>('/api/config')
  },
  saveCameraConfig(payload: CameraConfigRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/camera', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  saveRoi(payload: RoiConfigRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/roi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  clearRoi(): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/roi/clear', { method: 'POST' })
  },
  saveLine(payload: LineConfigRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/line', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  clearLine(): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/line/clear', { method: 'POST' })
  },
  saveOperatorZone(payload: OperatorZoneRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/operator_zone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  clearOperatorZone(): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/config/operator_zone/clear', { method: 'POST' })
  },
  getEvents(limit = 20): Promise<EventsResponse> {
    return requestJson<EventsResponse>(`/api/events?limit=${limit}`)
  },
  getDiagnostics(): Promise<DiagnosticsResponse> {
    return requestJson<DiagnosticsResponse>('/api/diagnostics/sysinfo')
  },
  startCalibration(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/calibrate/start', { method: 'POST' })
  },
  startMonitoring(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/monitor/start', { method: 'POST' })
  },
  stopMonitoring(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/monitor/stop', { method: 'POST' })
  },
  resetCalibration(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/reset_calibration', { method: 'POST' })
  },
  resetCounts(): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/reset_counts', { method: 'POST' })
  },
  adjustCount(payload: { delta: number }): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/adjust_count', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  restartVideo(): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/control/restart_video', { method: 'POST' })
  },
  setDemoPlaybackSpeed(payload: DemoPlaybackRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/control/demo/playback_speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  getDemoVideos(): Promise<DemoVideoListResponse> {
    return requestJson<DemoVideoListResponse>('/api/control/demo/videos')
  },
  uploadDemoVideo(file: File): Promise<OkResponse> {
    const body = new FormData()
    body.append('file', file)
    return requestJson<OkResponse>('/api/control/demo/videos/upload', {
      method: 'POST',
      body,
    })
  },
  selectDemoVideo(payload: DemoVideoSelectRequest): Promise<OkResponse> {
    return requestJson<OkResponse>('/api/control/demo/videos/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  setPersonIgnore(payload: PersonIgnoreRequest): Promise<StatusResponse> {
    return requestJson<StatusResponse>('/api/control/person_ignore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },
  testCamera(): Promise<CameraTestResponse> {
    return requestJson<CameraTestResponse>('/api/control/test_camera', { method: 'POST' })
  },
  snapshotUrl(cacheBust: number, overlayMode: 'default' | 'calibration' = 'default'): string {
    return `${API_BASE}/api/snapshot?t=${cacheBust}&overlay_mode=${overlayMode}`
  },
  liveStreamUrl(cacheBust: number, overlayMode: 'default' | 'calibration' = 'default'): string {
    return `${API_BASE}/api/stream.mjpg?t=${cacheBust}&overlay_mode=${overlayMode}`
  },
  debugSnapshotUrl(cacheBust: number, view: 'roi' | 'mask' | 'tracks' | 'people'): string {
    return `${API_BASE}/api/diagnostics/snapshot/debug?t=${cacheBust}&view=${view}`
  },
  activeDemoVideoUrl(cacheBust: number): string {
    return `${API_BASE}/api/control/demo/videos/active/content?t=${cacheBust}`
  },
  supportBundleUrl(): string {
    return `${API_BASE}/api/diagnostics/support_bundle.zip`
  },
  metricsWebSocketUrl(): string {
    const origin = BACKEND_ORIGIN || window.location.origin
    const url = new URL('/ws/metrics', origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    return url.toString()
  },
}
