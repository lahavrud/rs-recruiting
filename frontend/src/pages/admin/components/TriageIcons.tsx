// Inline SVG icons used across the triage UI. Hairline strokes, currentColor,
// aria-hidden — matches the brand's minimal feel. Kept in their own file so
// they're easy to scan and the main components file stays under the line limit.

export function IconClose({ className = "size-3.5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 4 L12 12 M12 4 L4 12" />
    </svg>
  );
}

export function IconCheck({ className = "size-5" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 8.5 L6.5 12 L13 4.5" />
    </svg>
  );
}

export function IconSparkle({ className = "size-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M8 1 L9.2 6 L14 7.2 L9.2 8.4 L8 13.4 L6.8 8.4 L2 7.2 L6.8 6 Z" />
    </svg>
  );
}

export function IconArrowRight({ className = "size-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 8 L13 8 M9 4 L13 8 L9 12" />
    </svg>
  );
}

export function IconDocument({ className = "size-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 2 H10 L13 5 V14 H4 Z M10 2 V5 H13 M6 9 H11 M6 11.5 H11" />
    </svg>
  );
}
