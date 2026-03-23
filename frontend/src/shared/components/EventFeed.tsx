import type { EventItem } from '../api/types.ts'

type EventFeedProps = {
  emptyMessage?: string
  events: EventItem[]
  title: string
  subtitle: string
}

function formatEventTime(value: string | null): string {
  if (!value) {
    return 'Waiting for timestamp'
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleString()
}

export function EventFeed({
  emptyMessage = 'No events yet.',
  events,
  title,
  subtitle,
}: EventFeedProps) {
  return (
    <aside className="content-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="panel-copy">{subtitle}</p>
        </div>
      </div>
      <ul className="event-list">
        {events.length === 0 ? (
          <li className="muted-note">{emptyMessage}</li>
        ) : (
          events.map((event) => (
            <li key={`${event.id ?? event.event_type}-${event.created_at ?? event.message}`} className="event-item">
              <div className="event-meta">{event.event_type}</div>
              <div>{event.message}</div>
              <div className="muted-note">{formatEventTime(event.created_at)}</div>
            </li>
          ))
        )}
      </ul>
    </aside>
  )
}
