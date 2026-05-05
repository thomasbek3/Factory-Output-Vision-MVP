import type { ConfigResponse, DiagnosticsResponse, LineDirection, StatusResponse } from './api/types.ts'

export function statusTone(state: string): 'green' | 'yellow' | 'red' | 'gray' {
  if (state === 'RUNNING_GREEN' || state === 'DEMO_COMPLETE' || state === 'DEMO_READY') {
    return 'green'
  }
  if (state === 'RUNNING_YELLOW_DROP' || state === 'RUNNING_YELLOW_RECONNECTING' || state === 'CALIBRATING') {
    return 'yellow'
  }
  if (state === 'RUNNING_RED_STOPPED') {
    return 'red'
  }
  return 'gray'
}

export function statusLabel(state: string): string {
  switch (state) {
    case 'RUNNING_GREEN':
      return 'Running normally'
    case 'RUNNING_YELLOW_DROP':
      return 'Slowing down'
    case 'RUNNING_YELLOW_RECONNECTING':
      return 'Reconnecting'
    case 'RUNNING_RED_STOPPED':
      return 'Stopped'
    case 'DEMO_COMPLETE':
      return 'Demo complete'
    case 'DEMO_READY':
      return 'Ready for demo'
    case 'CALIBRATING':
      return 'Calibrating'
    case 'IDLE':
      return 'Ready'
    case 'NOT_CONFIGURED':
      return 'Setup incomplete'
    default:
      return state
  }
}

export function statusGuidance(state: string): string {
  switch (state) {
    case 'RUNNING_GREEN':
      return 'Line is moving at a normal rate.'
    case 'RUNNING_YELLOW_DROP':
      return 'Output has slowed down. Check the line and the live view.'
    case 'RUNNING_YELLOW_RECONNECTING':
      return 'Video is reconnecting. Wait a moment, then refresh if it stays stuck.'
    case 'RUNNING_RED_STOPPED':
      return 'The backend sees the line as stopped. Check the live view and recent events.'
    case 'DEMO_COMPLETE':
      return 'Demo playback finished. The final count is frozen until you restart the demo.'
    case 'DEMO_READY':
      return 'Demo video is loaded. Click Start monitoring to run the live-counting demo.'
    case 'CALIBRATING':
      return 'Calibration is running. Keep the line moving normally until the baseline is set.'
    case 'IDLE':
      return 'Setup is saved. Start monitoring when you are ready.'
    case 'NOT_CONFIGURED':
      return 'Finish setup in the wizard before monitoring.'
    default:
      return 'Status is updating from the backend.'
  }
}

export function countSourceLabel(countSource: 'vision' | 'beam'): string {
  return countSource === 'beam' ? 'Beam Sensor' : 'Camera'
}

export function displayStateForContext(state: string, diagnostics: DiagnosticsResponse | null): string {
  const readyOnePassDemo =
    (state === 'NOT_CONFIGURED' || state === 'IDLE') &&
    diagnostics?.source_kind === 'demo' &&
    diagnostics.demo_video_name != null &&
    diagnostics.demo_count_mode === 'live_reader_snapshot' &&
    diagnostics.counting_mode === 'event_based' &&
    diagnostics.demo_loop_enabled === false

  return readyOnePassDemo ? 'DEMO_READY' : state
}

export function lineDirectionLabel(direction: LineDirection): string {
  switch (direction) {
    case 'both':
      return 'Count either direction'
    case 'left_to_right':
      return 'Count only left to right'
    case 'right_to_left':
      return 'Count only right to left'
    case 'top_to_bottom':
      return 'Count only top to bottom'
    case 'bottom_to_top':
      return 'Count only bottom to top'
    case 'p1_to_p2':
      return 'Count only first point to second point'
    case 'p2_to_p1':
      return 'Count only second point to first point'
    default:
      return direction
  }
}

export function statusNextSteps(state: string): string[] {
  switch (state) {
    case 'RUNNING_YELLOW_RECONNECTING':
      return ['Wait a few seconds for video to reconnect.', 'If it stays stuck, restart the video connection below.']
    case 'RUNNING_RED_STOPPED':
      return ['Check the line and current camera view.', 'If the line is healthy, reset calibration or return to the dashboard.']
    case 'RUNNING_YELLOW_DROP':
      return ['Check whether output is actually slowing down.', 'If counts look wrong, review the output area in setup.']
    case 'DEMO_COMPLETE':
      return ['Review the final total and recent events.', 'Use restart video or start monitoring again to replay the demo.']
    case 'CALIBRATING':
      return ['Let the line run normally until the baseline is set.', 'If the camera view looks wrong, restart video or return to setup.']
    case 'NOT_CONFIGURED':
      return ['Open the setup wizard.', 'Finish camera and output area before monitoring.']
    default:
      return ['Use the sections below to inspect camera health and recent events.', 'Download a support bundle if you need to escalate the issue.']
  }
}

export function countingGuidance(
  config: ConfigResponse | null,
  status: StatusResponse | null,
  diagnostics: DiagnosticsResponse | null,
): string[] {
  const hints: string[] = []
  const usesRuntimeCalibration = diagnostics?.source_kind === 'demo' && diagnostics?.counting_mode === 'event_based'

  if (!usesRuntimeCalibration && !config?.roi_polygon?.length) {
    hints.push('No output area is saved yet. Draw and save an ROI before expecting counts.')
  }

  if (!diagnostics?.reader_alive || status?.last_frame_age_sec == null) {
    hints.push('Video is not updating cleanly yet. Wait for a fresh frame before trusting counts.')
  }

  if (status?.counts_this_minute === 0 && status?.state.startsWith('RUNNING')) {
    if (usesRuntimeCalibration) {
      hints.push('Zero counts means no new carried-panel event has completed yet in this pass of the demo video.')
      hints.push('This demo path is counting from the runtime calibration file, not from a dashboard-drawn ROI.')
    } else {
      hints.push('Zero counts means no new object has been detected in the output zone yet.')
      hints.push('Make sure objects are clearly visible inside the output area.')
    }

    if (diagnostics?.person_ignore_enabled) {
      hints.push('Person-ignore masking is on. If the person fully hides the product, the counter still will not see the part clearly.')
    }

    if (diagnostics?.source_kind === 'demo' && !usesRuntimeCalibration) {
      hints.push('On the bundled demo clip, draw the output area over the region where parts appear.')
    }
  }

  if (status?.state === 'RUNNING_RED_STOPPED') {
    hints.push('Stopped means no new objects detected recently. Recheck the output area and camera view before recalibrating.')
  }

  return [...new Set(hints)].slice(0, 4)
}
