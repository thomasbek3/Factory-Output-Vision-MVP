import { useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'

import type { Point } from '../api/types.ts'
import type { LiveOverlayShape } from '../liveOverlays.ts'

type LiveMedia =
  | {
      kind: 'image'
      src: string
    }
  | {
      kind: 'video'
      fallbackImageSrc?: string
      src: string
      playbackRate?: number
      showNativeControls?: boolean
    }

type LiveSnapshotPanelProps = {
  controls?: ReactNode
  editor?: {
    draftPoints: Point[]
    hint?: string
    mode: 'polygon' | 'line'
    onDraftPointsChange: (points: Point[]) => void
  }
  frameAgeSec: number | null | undefined
  media: LiveMedia
  onRefresh: () => void
  overlays?: LiveOverlayShape[]
  refreshLabel?: string
  subtitle: string
  title: string
}

type Dimensions = {
  width: number
  height: number
}

type VideoState = {
  fallbackActive: boolean
  mediaKey: string
  ready: boolean
}

function pointToPercent(point: { x: number; y: number }): string {
  return `${point.x * 100},${point.y * 100}`
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function fitContain(container: Dimensions, media: Dimensions): Dimensions & { left: number; top: number } {
  if (container.width <= 0 || container.height <= 0 || media.width <= 0 || media.height <= 0) {
    return { left: 0, top: 0, width: container.width, height: container.height }
  }

  const containerRatio = container.width / container.height
  const mediaRatio = media.width / media.height

  if (mediaRatio > containerRatio) {
    const width = container.width
    const height = width / mediaRatio
    return { left: 0, top: (container.height - height) / 2, width, height }
  }

  const height = container.height
  const width = height * mediaRatio
  return { left: (container.width - width) / 2, top: 0, width, height }
}

export function LiveSnapshotPanel({
  controls,
  editor,
  frameAgeSec,
  media,
  onRefresh,
  overlays = [],
  refreshLabel,
  subtitle,
  title,
}: LiveSnapshotPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const frameRef = useRef<HTMLDivElement | null>(null)
  const [containerSize, setContainerSize] = useState<Dimensions>({ width: 0, height: 0 })
  const [mediaSize, setMediaSize] = useState<Dimensions>({ width: 0, height: 0 })
  const mediaKey = `${media.kind}:${media.src}`
  const [videoState, setVideoState] = useState<VideoState>({ fallbackActive: false, mediaKey, ready: false })
  const videoPlaybackRate = media.kind === 'video' ? media.playbackRate : undefined
  const fallbackImageSrc = media.kind === 'video' ? media.fallbackImageSrc : undefined
  const videoReady = videoState.mediaKey === mediaKey && videoState.ready
  const videoFallbackActive = videoState.mediaKey === mediaKey && videoState.fallbackActive
  const showFallbackImage = media.kind === 'video' && videoFallbackActive && Boolean(fallbackImageSrc)

  function updateVideoState(nextState: Partial<Omit<VideoState, 'mediaKey'>>): void {
    setVideoState((current) => {
      const currentForMedia = current.mediaKey === mediaKey ? current : { fallbackActive: false, mediaKey, ready: false }
      return { ...currentForMedia, ...nextState }
    })
  }

  useEffect(() => {
    if (media.kind !== 'video' || !videoRef.current) {
      return
    }
    videoRef.current.playbackRate = videoPlaybackRate ?? 1
  }, [media.kind, videoPlaybackRate])

  useEffect(() => {
    if (media.kind !== 'video' || !videoRef.current) {
      return
    }
    const playPromise = videoRef.current.play()
    if (playPromise) {
      void playPromise.catch(() => {
        // Native autoplay can be blocked; keep controls available in that case.
      })
    }
  }, [media.kind, media.src])

  useEffect(() => {
    if (media.kind !== 'video' || !fallbackImageSrc || videoReady || videoFallbackActive) {
      return
    }

    const timeout = window.setTimeout(() => {
      setVideoState((current) => {
        const currentForMedia = current.mediaKey === mediaKey ? current : { fallbackActive: false, mediaKey, ready: false }
        if (currentForMedia.ready) {
          return currentForMedia
        }
        return { ...currentForMedia, fallbackActive: true }
      })
    }, 2500)

    return () => {
      window.clearTimeout(timeout)
    }
  }, [fallbackImageSrc, media.kind, mediaKey, videoFallbackActive, videoReady])

  useEffect(() => {
    const frame = frameRef.current
    if (!frame) {
      return
    }

    const updateSize = () => {
      const rect = frame.getBoundingClientRect()
      setContainerSize({ width: rect.width, height: rect.height })
    }

    updateSize()
    const observer = new ResizeObserver(() => updateSize())
    observer.observe(frame)
    return () => observer.disconnect()
  }, [])

  const actionLabel = refreshLabel ?? (media.kind === 'video' ? 'Reload video' : 'Refresh snapshot')
  const overlayBox = useMemo(() => fitContain(containerSize, mediaSize), [containerSize, mediaSize])
  const draftOverlay = useMemo<LiveOverlayShape | null>(() => {
    if (!editor || editor.draftPoints.length === 0) {
      return null
    }

    if (editor.mode === 'polygon') {
      return {
        kind: 'polygon',
        color: '#ef6c2f',
        dashed: true,
        label: 'Draft output area',
        points: editor.draftPoints,
      }
    }

    if (editor.draftPoints.length < 2) {
      return null
    }

    return {
      kind: 'line',
      color: '#ef6c2f',
      dashed: true,
      label: 'Draft count line',
      line: {
        p1: editor.draftPoints[0],
        p2: editor.draftPoints[1],
      },
    }
  }, [editor])
  const renderOverlays = draftOverlay ? [...overlays, draftOverlay] : overlays

  function handleFrameClick(event: MouseEvent<HTMLDivElement>): void {
    if (!editor || overlayBox.width <= 0 || overlayBox.height <= 0) {
      return
    }

    const frame = frameRef.current
    if (!frame) {
      return
    }

    const rect = frame.getBoundingClientRect()
    const left = rect.left + overlayBox.left
    const top = rect.top + overlayBox.top
    const right = left + overlayBox.width
    const bottom = top + overlayBox.height

    if (event.clientX < left || event.clientX > right || event.clientY < top || event.clientY > bottom) {
      return
    }

    const point = {
      x: clamp((event.clientX - left) / overlayBox.width),
      y: clamp((event.clientY - top) / overlayBox.height),
    }

    if (editor.mode === 'polygon') {
      editor.onDraftPointsChange([...editor.draftPoints, point])
      return
    }

    if (editor.draftPoints.length >= 2) {
      editor.onDraftPointsChange([point])
      return
    }

    editor.onDraftPointsChange([...editor.draftPoints, point])
  }

  return (
    <aside className="content-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="panel-copy">{subtitle}</p>
        </div>
        <div className="inline-actions">
          {controls}
          <button onClick={onRefresh} type="button">
            {actionLabel}
          </button>
        </div>
      </div>
      <div
        className={`snapshot-frame live-snapshot-frame${editor ? ' live-editor-active' : ''}`}
        onClick={handleFrameClick}
        ref={frameRef}
      >
        {media.kind === 'video' && !showFallbackImage ? (
          <video
            autoPlay
            controls={media.showNativeControls ?? false}
            key={media.src}
            loop
            muted
            onCanPlay={() => {
              updateVideoState({ ready: true })
            }}
            onError={() => {
              if (fallbackImageSrc) {
                updateVideoState({ fallbackActive: true })
              }
            }}
            onLoadedData={() => {
              updateVideoState({ ready: true })
            }}
            onLoadedMetadata={(event) => {
              const element = event.currentTarget
              setMediaSize({
                width: element.videoWidth || element.clientWidth,
                height: element.videoHeight || element.clientHeight,
              })
            }}
            onPlaying={() => {
              updateVideoState({ ready: true })
            }}
            playsInline
            preload="auto"
            ref={videoRef}
            src={media.src}
          />
        ) : (
          <img
            alt="Live factory snapshot"
            onLoad={(event) => {
              const element = event.currentTarget
              setMediaSize({
                width: element.naturalWidth || element.clientWidth,
                height: element.naturalHeight || element.clientHeight,
              })
            }}
            src={showFallbackImage ? fallbackImageSrc : media.src}
          />
        )}
        {renderOverlays.length > 0 ? (
          <svg
            aria-hidden="true"
            className="annotator-svg live-overlay-svg"
            preserveAspectRatio="none"
            style={{
              left: `${overlayBox.left}px`,
              top: `${overlayBox.top}px`,
              width: `${overlayBox.width}px`,
              height: `${overlayBox.height}px`,
            }}
            viewBox="0 0 100 100"
          >
            {renderOverlays.map((overlay) => {
              if (overlay.kind === 'polygon') {
                return (
                  <g key={`${overlay.label}-${overlay.color}`}>
                    {overlay.points.length >= 3 ? (
                      <polygon
                        className="annotator-shape"
                        points={overlay.points.map(pointToPercent).join(' ')}
                        stroke={overlay.color}
                        strokeDasharray={overlay.dashed ? '3 2' : undefined}
                      />
                    ) : (
                      <polyline
                        className="annotator-shape"
                        points={overlay.points.map(pointToPercent).join(' ')}
                        stroke={overlay.color}
                        strokeDasharray={overlay.dashed ? '3 2' : undefined}
                      />
                    )}
                    {overlay.points.map((point, index) => (
                      <circle cx={point.x * 100} cy={point.y * 100} fill={overlay.color} key={`${overlay.label}-${index}`} r="1.2" />
                    ))}
                  </g>
                )
              }

              return (
                <g key={`${overlay.label}-${overlay.color}`}>
                  <line
                    className="annotator-shape"
                    stroke={overlay.color}
                    strokeDasharray={overlay.dashed ? '3 2' : undefined}
                    x1={overlay.line.p1.x * 100}
                    x2={overlay.line.p2.x * 100}
                    y1={overlay.line.p1.y * 100}
                    y2={overlay.line.p2.y * 100}
                  />
                  <circle cx={overlay.line.p1.x * 100} cy={overlay.line.p1.y * 100} fill={overlay.color} r="1.2" />
                  <circle cx={overlay.line.p2.x * 100} cy={overlay.line.p2.y * 100} fill={overlay.color} r="1.2" />
                </g>
              )
            })}
          </svg>
        ) : null}
        {editor?.hint ? <div className="annotator-overlay-note">{editor.hint}</div> : null}
      </div>
      <div className="detail-list compact-detail-list">
        <div className="detail-row">
          <span className="detail-label">Frame age</span>
          <span className="detail-value">{frameAgeSec == null ? 'Waiting for video' : `${frameAgeSec}s`}</span>
        </div>
      </div>
    </aside>
  )
}
