import type { ReactNode } from "react";

import { formatDate } from "@/utils/formatDate";

interface ActivityTimelineEvent {
  id: number;
  created_at: string;
}

interface Props<T extends ActivityTimelineEvent> {
  events: T[] | null;
  error: boolean;
  emptyMessage: string;
  errorMessage: string;
  loadingMessage: string;
  /** Per-item content, rendered after the timeline dot and before the formatted date. */
  renderItem: (event: T) => ReactNode;
}

/** Shared dot-and-connector timeline shell for record-pane activity panels. */
export default function ActivityTimeline<T extends ActivityTimelineEvent>({
  events,
  error,
  emptyMessage,
  errorMessage,
  loadingMessage,
  renderItem,
}: Props<T>) {
  if (error) {
    return <p className="mt-3 text-xs text-danger">{errorMessage}</p>;
  }
  if (events == null) {
    return <p className="mt-3 text-xs text-white/35">{loadingMessage}</p>;
  }
  if (events.length === 0) {
    return <p className="mt-3 text-xs text-white/35">{emptyMessage}</p>;
  }

  return (
    <ul className="mt-3 space-y-4">
      {events.map((event, i) => (
        <li key={event.id} className="relative ps-5">
          {i < events.length - 1 && (
            <span className="absolute start-[3px] top-3 h-full w-px bg-white/8" aria-hidden />
          )}
          <span
            className="absolute start-0 top-1.5 size-1.5 rounded-full bg-copper/60"
            aria-hidden
          />
          {renderItem(event)}
          <p className="mt-1 text-xs text-white/35">{formatDate(event.created_at)}</p>
        </li>
      ))}
    </ul>
  );
}
