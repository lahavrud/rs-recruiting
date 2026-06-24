/** Sidebar-panel glyph for the candidates rail show/hide toggle. `flipped` mirrors it for the "show" state. */
export default function RailToggleIcon({
  className,
  flipped,
}: {
  className?: string;
  flipped?: boolean;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${className ?? ""} transition-transform duration-300 ease-in-out ${flipped ? "-scale-x-100" : ""}`}
      aria-hidden="true"
    >
      <path d="M6 4 L10 8 L6 12" />
      <path d="M9.5 4 L13.5 8 L9.5 12" />
    </svg>
  );
}
