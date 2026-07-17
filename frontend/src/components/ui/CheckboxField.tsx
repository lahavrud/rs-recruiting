/** A checkbox with its label — the admin filter panels' boolean filter. */
export default function CheckboxField({
  checked,
  onChange,
  label,
  className = "",
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  className?: string;
}) {
  return (
    <label
      className={`inline-flex cursor-pointer items-center gap-2 text-sm text-white/80 ${className}`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-4 rounded border-white/20 bg-well text-copper focus:ring-copper"
      />
      {label}
    </label>
  );
}
