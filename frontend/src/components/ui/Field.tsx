import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";

interface FieldProps {
  label: string;
  /**
   * When set, renders as `<div>` wrapper with explicit `<label htmlFor={id}>`.
   * Use for inputs that need an explicit id (autocomplete, ARIA, or complex
   * children where wrapping in `<label>` would break semantics).
   *
   * When omitted, renders as a `<label>` that implicitly associates with its
   * single descendant input.
   */
  id?: string;
  /** Maps to `data-field` for `focusFirstError` lookups. Falls back to `id`. */
  name?: string;
  /** Spans two columns in a `sm:grid-cols-2` layout. */
  full?: boolean;
  required?: boolean;
  optional?: boolean;
  /** Inline validation error shown below the field. */
  error?: string;
  /** Subtle hint shown below the field. */
  hint?: string;
  className?: string;
  children: ReactNode;
}

/**
 * Canonical form field wrapper — label, optional/required adornment, error,
 * and hint. Tag switches between `<div>` (when `id` is set, with explicit
 * `htmlFor`) and `<label>` (implicit association).
 */
export default function Field({
  label,
  id,
  name,
  full,
  required,
  optional,
  error,
  hint,
  className,
  children,
}: FieldProps) {
  const { t } = useTranslation(['common', 'sm']);
  const dataField = name ?? id;
  const colSpanCls = full ? "sm:col-span-2" : "";

  const labelRow = (
    <>
      <span>{label}</span>
      {required && <span className="text-copper/80">*</span>}
      {optional && (
        <span className="text-[10px] text-white/30">({t("common:optional")})</span>
      )}
    </>
  );

  if (id !== undefined) {
    return (
      <div data-field={dataField} className={`${colSpanCls} ${className ?? ""}`.trim() || undefined}>
        <label
          htmlFor={id}
          className="flex items-center gap-1.5 text-xs text-white/55 sm:text-sm"
        >
          {labelRow}
        </label>
        <div className="mt-1.5">{children}</div>
        {error && <p className="mt-1 text-xs text-danger">{error}</p>}
        {hint && <p className="mt-1 text-[11px] text-white/30">{hint}</p>}
      </div>
    );
  }

  return (
    <label data-field={dataField} className={`block ${colSpanCls} ${className ?? ""}`.trim()}>
      <span className="flex items-center gap-1.5 text-xs text-white/55">
        {labelRow}
      </span>
      <span className="mt-1 block">{children}</span>
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
      {hint && <span className="mt-1 block text-[11px] text-white/30">{hint}</span>}
    </label>
  );
}
