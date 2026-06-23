import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { inputCls, selectCls } from "@/styles/forms";

interface Option<T> {
  value: T;
  label: string;
}

interface Props<T> {
  value: T | null;
  onChange: (v: T | null) => void;
  options: Option<T>[];
  placeholder: string;
  searchPlaceholder?: string;
}

/**
 * Lightweight searchable select. Renders the trigger inline like a native
 * <select>, but pops the option list as a fixed-position element via portal
 * so it escapes any `overflow-hidden` ancestor (e.g. the animated filter
 * panel) and always stacks above sibling content.
 */
export default function SearchableSelect<T extends string | number>({
  value,
  onChange,
  options,
  placeholder,
  searchPlaceholder,
}: Props<T>) {
  const { t } = useTranslation(['common', 'http']);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);

  function close() {
    setOpen(false);
    setQuery("");
  }

  // Recompute trigger position when opening + on scroll/resize so the
  // popover stays glued to the trigger as the page moves under it.
  useLayoutEffect(() => {
    if (!open) return;
    function measure() {
      const el = triggerRef.current;
      if (el) setRect(el.getBoundingClientRect());
    }
    measure();
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent | TouchEvent) {
      const target = e.target as Node;
      if (
        !triggerRef.current?.contains(target) &&
        !popoverRef.current?.contains(target)
      ) {
        close();
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    const id = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.clearTimeout(id);
    };
  }, [open]);

  const selected = useMemo(
    () => options.find((o) => o.value === value),
    [options, value],
  );
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`${selectCls} flex w-full items-center justify-between gap-2 text-start transition-colors duration-200 active:scale-[0.99] ${open ? "border-copper/40" : ""}`}
      >
        <span className={selected ? "truncate text-white/85" : "truncate text-white/40"}>
          {selected ? selected.label : placeholder}
        </span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`size-3.5 shrink-0 text-white/40 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {createPortal(
        <div
          ref={popoverRef}
          aria-hidden={!open}
          style={
            rect
              ? {
                  position: "fixed",
                  top: rect.bottom + 4,
                  left: rect.left,
                  width: rect.width,
                }
              : { position: "fixed", visibility: "hidden" }
          }
          className={`z-[100] origin-top overflow-hidden rounded-md border border-white/10 bg-card-raised shadow-2xl shadow-black/60 transition duration-150 ease-out ${
            open
              ? "opacity-100 translate-y-0 pointer-events-auto"
              : "opacity-0 -translate-y-1 pointer-events-none"
          }`}
        >
          <div className="border-b border-white/8 p-2">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={searchPlaceholder ?? t("common:searchPlaceholder")}
              className={inputCls}
            />
          </div>
          <div role="listbox" className="max-h-60 overflow-y-auto py-1">
            {value !== null && (
              <button
                type="button"
                onClick={() => {
                  onChange(null);
                  close();
                }}
                className="block w-full px-3 py-1.5 text-start text-xs text-white/40 transition hover:bg-white/5"
              >
                {placeholder}
              </button>
            )}
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-white/30">
                {t("common:noResultsHeadline")}
              </p>
            ) : (
              filtered.map((o) => (
                <button
                  key={String(o.value)}
                  type="button"
                  role="option"
                  aria-selected={o.value === value}
                  onClick={() => {
                    onChange(o.value);
                    close();
                  }}
                  className={`block w-full truncate px-3 py-1.5 text-start text-sm transition hover:bg-white/5 ${
                    o.value === value ? "bg-copper/10 text-copper" : "text-white/80"
                  }`}
                >
                  {o.label}
                </button>
              ))
            )}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
