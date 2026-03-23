import { startTransition, useCallback, useEffect, useState } from 'react'

import { apiClient } from '../../shared/api/client.ts'
import type { ConfigResponse, DemoVideoItem, DiagnosticsResponse, EventItem, LineDirection, Point, StatusResponse } from '../../shared/api/types.ts'

const eventLimit = 12

export type TroubleshootingNotice = {
  tone: 'info' | 'success' | 'error'
  message: string
}

function toMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function useTroubleshootingData() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [demoVideos, setDemoVideos] = useState<DemoVideoItem[]>([])
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [notice, setNotice] = useState<TroubleshootingNotice | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [snapshotTick, setSnapshotTick] = useState(0)
  const [videoTick, setVideoTick] = useState(0)

  const refresh = useCallback(async () => {
    const [statusResponse, configResponse, diagnosticsResponse, eventsResponse, demoVideosResponse] = await Promise.all([
      apiClient.getStatus(),
      apiClient.getConfig(),
      apiClient.getDiagnostics(),
      apiClient.getEvents(eventLimit),
      apiClient.getDemoVideos(),
    ])
    startTransition(() => {
      setStatus(statusResponse)
      setConfig(configResponse)
      setDiagnostics(diagnosticsResponse)
      setEvents(eventsResponse.items)
      setDemoVideos(demoVideosResponse.items)
    })
  }, [])

  useEffect(() => {
    let active = true

    void (async () => {
      try {
        await refresh()
        if (!active) {
          return
        }
        setNotice(null)
      } catch (error) {
        if (!active) {
          return
        }
        setNotice({ tone: 'error', message: toMessage(error, 'Unable to load troubleshooting data.') })
      }
    })()

    return () => {
      active = false
    }
  }, [refresh])

  useEffect(() => {
    let active = true

    const timer = window.setInterval(() => {
      void (async () => {
        try {
          await refresh()
        } catch (error) {
          if (!active) {
            return
          }
          setNotice((current) => current ?? { tone: 'error', message: toMessage(error, 'Unable to refresh troubleshooting data.') })
        }
      })()
    }, 8000)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [refresh])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSnapshotTick(Date.now())
    }, 1000)

    return () => {
      window.clearInterval(timer)
    }
  }, [])

  async function runAction(
    action: string,
    operation: () => Promise<unknown>,
    successMessage: string,
    options: { refreshSnapshots?: boolean; refreshVideo?: boolean } = {},
  ): Promise<boolean> {
    const { refreshSnapshots = true, refreshVideo = false } = options
    setBusyAction(action)
    try {
      await operation()
      await refresh()
      if (refreshSnapshots) {
        setSnapshotTick(Date.now())
      }
      if (refreshVideo) {
        setVideoTick(Date.now())
      }
      setNotice({ tone: 'success', message: successMessage })
      return true
    } catch (error) {
      setNotice({ tone: 'error', message: toMessage(error, 'Unable to complete maintenance action.') })
      return false
    } finally {
      setBusyAction(null)
    }
  }

  async function restartVideo(): Promise<boolean> {
    return runAction('restart-video', () => apiClient.restartVideo(), 'Video connection restart requested.', {
      refreshVideo: true,
    })
  }

  async function resetCalibration(): Promise<boolean> {
    return runAction('reset-calibration', () => apiClient.resetCalibration(), 'Calibration baseline reset.')
  }

  async function resetCounts(): Promise<boolean> {
    return runAction('reset-counts', () => apiClient.resetCounts(), 'Runtime counts reset.')
  }

  async function saveRoi(roiPolygon: Point[]): Promise<boolean> {
    return runAction('roi-save', () => apiClient.saveRoi({ roi_polygon: roiPolygon }), 'Output area saved from live view.')
  }

  async function clearRoi(): Promise<boolean> {
    return runAction('roi-clear', () => apiClient.clearRoi(), 'Output area cleared.')
  }

  async function saveLine(p1: Point, p2: Point, direction: LineDirection): Promise<boolean> {
    return runAction('line-save', () => apiClient.saveLine({ p1, p2, direction }), 'Count line saved from live view.')
  }

  async function clearLine(): Promise<boolean> {
    return runAction('line-clear', () => apiClient.clearLine(), 'Count line cleared.')
  }

  async function setDemoPlaybackSpeed(speedMultiplier: number): Promise<boolean> {
    return runAction(
      `playback-speed-${speedMultiplier}`,
      () => apiClient.setDemoPlaybackSpeed({ speed_multiplier: speedMultiplier }),
      `Demo playback speed set to ${speedMultiplier}x.`,
    )
  }

  async function setPersonIgnore(enabled: boolean): Promise<boolean> {
    return runAction(
      enabled ? 'enable-person-ignore' : 'disable-person-ignore',
      () => apiClient.setPersonIgnore({ enabled }),
      enabled ? 'Person-ignore masking enabled.' : 'Person-ignore masking disabled.',
    )
  }

  async function uploadDemoVideo(file: File): Promise<boolean> {
    return runAction('upload-demo-video', () => apiClient.uploadDemoVideo(file), `Uploaded and selected ${file.name}.`, {
      refreshVideo: true,
    })
  }

  async function selectDemoVideo(path: string, name: string): Promise<boolean> {
    return runAction('select-demo-video', () => apiClient.selectDemoVideo({ path }), `Selected ${name} as the active demo video.`, {
      refreshVideo: true,
    })
  }

  return {
    busyAction,
    clearLine,
    clearRoi,
    config,
    demoVideos,
    diagnostics,
    events,
    notice,
    refresh,
    refreshSnapshot: () => {
      setSnapshotTick(Date.now())
      setVideoTick(Date.now())
    },
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
  }
}
