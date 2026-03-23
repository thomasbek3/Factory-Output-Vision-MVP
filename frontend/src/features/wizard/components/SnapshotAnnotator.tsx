import { useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'

import type { CountLine, Point } from '../../../shared/api/types.ts'

type OverlayShape =
  | {
      kind: 'polygon'
      color: string
      label: string
      points: Point[]
      dashed?: boolean
    }
  | {
      kind: 'line'
      color: string
      label: string
      line: CountLine | { p1: Point; p2: Point }
      dashed?: boolean
    }

type SnapshotAnnotatorProps = {
  mode: 'polygon' | 'line'
  draftPoints: Point[]
  overlays: OverlayShape[]
  imageSrc: string
  title: string
  subtitle: string
  onDraftPointsChange: (points: Point[]) => void
  onRefresh: () => void
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function pointToPercent(point: Point): string {
  return `${point.x * 100},${point.y * 100}`
}

function polygonDraftLabel(mode: 'polygon' | 'line'): string {
  return mode === 'polygon' ? 'Draft area' : 'Draft line'
}

export function SnapshotAnnotator({
  mode,
  draftPoints,
  overlays,
  imageSrc,
  title,
  subtitle,
  onDraftPointsChange,
  onRefresh,
}: SnapshotAnnotatorProps) {
  const frameRef = useRef<HTMLDivElement | null>(null)
  const [imageReady, setImageReady] = useState(false)
  const [imageError, setImageError] = useState(false)

  const draftOverlay = useMemo<OverlayShape | null>(() => {
    if (mode === 'polygon') {
      if (draftPoints.length === 0) {
        return null
      }
      return {
        kind: 'polygon',
        color: '#ef6c2f',
        label: polygonDraftLabel(mode),
        points: draftPoints,
        dashed: true,
      }
    }

    if (draftPoints.length < 2) {
      return null
    }

    return {
      kind: 'line',
      color: '#ef6c2f',
      label: polygonDraftLabel(mode),
      line: { p1: draftPoints[0], p2: draftPoints[1] },
      dashed: true,
    }
  }, [draftPoints, mode])

  const renderOverlays = draftOverlay ? [...overlays, draftOverlay] : overlays

  function handleFrameClick(event: MouseEvent<HTMLDivElement>): void {
    const frame = frameRef.current
    if (!frame) {
      return
    }

    const rect = frame.getBoundingClientRect()
    const point = {
      x: clamp((event.clientX - rect.left) / rect.width),
      y: clamp((event.clientY - rect.top) / rect.height),
    }

    if (mode === 'polygon') {
      onDraftPointsChange([...draftPoints, point])
      return
    }

    if (draftPoints.length >= 2) {
      onDraftPointsChange([point])
      return
    }

    onDraftPointsChange([...draftPoints, point])
  }

  return (
    <div className="annotator-card">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">{title}</h3>
          <p className="panel-copy">{subtitle}</p>
        </div>
        <button onClick={onRefresh} type="button">
          Refresh snapshot
        </button>
      </div>
      <div
        aria-label={title}
        className={`annotator-frame${mode === 'line' ? ' line-mode' : ''}`}
        onClick={handleFrameClick}
        ref={frameRef}
      >
        <img
          alt="Factory camera snapshot"
          onError={() => {
            setImageError(true)
            setImageReady(false)
          }}
          onLoad={() => {
            setImageError(false)
            setImageReady(true)
          }}
          src={imageSrc}
        />
        <svg aria-hidden="true" className="annotator-svg" preserveAspectRatio="none" viewBox="0 0 100 100">
          {renderOverlays.map((overlay) => {
            if (overlay.kind === 'polygon') {
              const points = overlay.points.map(pointToPercent).join(' ')
              const isClosed = overlay.points.length >= 3
              return (
                <g key={`${overlay.label}-${overlay.color}`}>
                  {isClosed ? (
                    <polygon
                      className="annotator-shape"
                      points={points}
                      stroke={overlay.color}
                      strokeDasharray={overlay.dashed ? '3 2' : undefined}
                    />
                  ) : (
                    <polyline
                      className="annotator-shape"
                      points={points}
                      stroke={overlay.color}
                      strokeDasharray={overlay.dashed ? '3 2' : undefined}
                    />
                  )}
                  {overlay.points.map((point, index) => (
                    <circle
                      cx={point.x * 100}
                      cy={point.y * 100}
                      fill={overlay.color}
                      key={`${overlay.label}-${index}`}
                      r="1.2"
                    />
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
        {!imageReady && !imageError ? <div className="annotator-overlay-note">Loading snapshot...</div> : null}
        {imageError ? (
          <div className="annotator-overlay-note error">Snapshot is not ready yet. Refresh and try again.</div>
        ) : null}
      </div>
      <div className="annotator-legend">
        {renderOverlays.length === 0 ? (
          <span className="muted-note">No saved overlays yet.</span>
        ) : (
          renderOverlays.map((overlay) => (
            <span className="annotator-legend-item" key={`${overlay.label}-${overlay.color}`}>
              <span className="annotator-legend-swatch" style={{ backgroundColor: overlay.color }} />
              {overlay.label}
            </span>
          ))
        )}
      </div>
    </div>
  )
}
