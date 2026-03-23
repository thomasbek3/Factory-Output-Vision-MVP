import type { ConfigResponse, CountLine, Point } from './api/types.ts'

export type LiveOverlayShape =
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

function hasPolygon(points: Point[] | null | undefined): boolean {
  return Boolean(points && points.length >= 3)
}

function hasLine(line: CountLine | null | undefined): boolean {
  return Boolean(line?.p1 && line?.p2)
}

export function buildSavedGeometryOverlays(config: ConfigResponse | null): LiveOverlayShape[] {
  if (!config) {
    return []
  }

  const overlays: LiveOverlayShape[] = []

  if (hasPolygon(config.roi_polygon)) {
    overlays.push({
      kind: 'polygon',
      color: '#1f9d55',
      label: 'Saved output area',
      points: config.roi_polygon ?? [],
    })
  }

  if (hasLine(config.line)) {
    overlays.push({
      kind: 'line',
      color: '#f59e0b',
      label: 'Saved count line',
      line: config.line as CountLine,
    })
  }

  if (config.operator_zone.enabled && hasPolygon(config.operator_zone.polygon)) {
    overlays.push({
      kind: 'polygon',
      color: '#2563eb',
      label: 'Saved operator zone',
      points: config.operator_zone.polygon ?? [],
    })
  }

  return overlays
}
