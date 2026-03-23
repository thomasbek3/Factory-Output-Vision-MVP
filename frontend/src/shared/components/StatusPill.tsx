import { statusLabel, statusTone } from '../status.ts'

type StatusPillProps = {
  state: string
}

function dotClassName(state: string): string {
  return `status-dot ${statusTone(state)}`
}

export function StatusPill({ state }: StatusPillProps) {
  return (
    <span className="status-pill">
      <span className={dotClassName(state)} />
      <span>{statusLabel(state)}</span>
    </span>
  )
}
