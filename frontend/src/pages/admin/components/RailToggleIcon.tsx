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
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${className ?? ""} transition-transform duration-300 ease-in-out ${flipped ? "-scale-x-100" : ""}`}
      aria-hidden="true"
    >
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
      <path d="M6 2.5 V13.5" />
      <path d="M3 6 L4.5 7.5 L3 9" />
    </svg>
  );
}
