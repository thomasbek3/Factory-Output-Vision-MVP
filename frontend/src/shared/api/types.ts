export type CountSource = 'vision' | 'beam'

export type Point = {
  x: number
  y: number
}

export type StreamProfile = 'sub' | 'main'

export type LineDirection =
  | 'both'
  | 'left_to_right'
  | 'right_to_left'
  | 'top_to_bottom'
  | 'bottom_to_top'
  | 'p1_to_p2'
  | 'p2_to_p1'

export type CountLine = {
  p1: Point
  p2: Point
  direction: LineDirection
}

export type OperatorZone = {
  enabled: boolean
  polygon: Point[] | null
}

export type StatusResponse = {
  state: string
  count_source: CountSource
  baseline_rate_per_min: number | null
  calibration_progress_pct: number
  calibration_elapsed_sec: number
  calibration_target_duration_sec: number
  rolling_rate_per_min: number
  counts_this_minute: number
  counts_this_hour: number
  runtime_total: number
  proof_backed_total: number
  runtime_inferred_only: number
  last_frame_age_sec: number | null
  reconnect_attempts_total: number
  operator_absent: boolean
}

export type ConfigResponse = {
  id: number
  camera_ip: string | null
  camera_username: string | null
  camera_password: string | null
  baseline_rate_per_min: number | null
  stream_profile: StreamProfile | null
  roi_polygon: Point[] | null
  line: CountLine | null
  operator_zone: OperatorZone
}

export type CameraConfigRequest = {
  camera_ip: string
  camera_username: string
  camera_password: string
  stream_profile: StreamProfile
}

export type RoiConfigRequest = {
  roi_polygon: Point[]
}

export type LineConfigRequest = {
  p1: Point
  p2: Point
  direction: LineDirection
}

export type OperatorZoneRequest = {
  enabled: boolean
  polygon?: Point[] | null
}

export type DemoPlaybackRequest = {
  speed_multiplier: number
}

export type PersonIgnoreRequest = {
  enabled: boolean
}

export type DemoVideoItem = {
  name: string
  path: string
  size_bytes: number
  modified_at: string
  selected: boolean
  managed: boolean
}

export type DemoVideoListResponse = {
  items: DemoVideoItem[]
}

export type DemoVideoSelectRequest = {
  path: string
}

export type EventItem = {
  id: number | null
  event_type: string
  state_from: string | null
  state_to: string | null
  message: string
  created_at: string | null
}

export type MetricsEvent = {
  type: string
  state_from: string | null
  state_to: string | null
  message: string
}

export type MetricsPayload = StatusResponse & {
  last_event?: MetricsEvent
}

export type EventsResponse = {
  items: EventItem[]
  limit: number
}

export type CameraTestResponse = {
  ok: boolean
  message: string
  action_hint: string | null
  details: Record<string, unknown> | null
}

export type DiagnosticsResponse = {
  app_version: string
  uptime_sec: number
  current_state: string
  count_source: CountSource
  counting_mode: string
  last_frame_age_sec: number | null
  reconnect_attempts_total: number
  reader_alive: boolean
  vision_loop_alive: boolean
  person_detect_loop_alive: boolean
  db_path: string
  log_directory: string
  source_kind: 'camera' | 'demo'
  demo_playback_speed: number
  demo_video_name: string | null
  demo_count_mode: string
  demo_loop_enabled: boolean
  demo_playback_finished: boolean
  demo_receipt_total: number
  demo_revealed_receipts: number
  demo_expected_final_total: number
  demo_count_report: string | null
  person_ignore_enabled: boolean
  people_detected_count: number
  latest_error_code: string | null
  latest_error_message: string | null
}

export type ManualCountAdjustRequest = {
  delta: number
}

export type OkResponse = {
  ok: boolean
}
