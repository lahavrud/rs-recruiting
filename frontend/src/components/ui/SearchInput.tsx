import { useEffect, useRef, useState } from "react";

import { useTranslation } from "react-i18next";

import { useDebounce } from "@/hooks/useDebounce";
import { INPUT_CLS } from "@/styles/forms";

interface SearchInputProps {
  /** Initial value, used only for uncontrolled internal state. */
  initialValue?: string;
  /** Controlled value. When provided, debounce is bypassed and onChange fires synchronously. */
  value?: string;
  /** Fired with the debounced value (or synchronously when controlled). */
  onChange: (value: string) => void;
  /** Override the default Hebrew placeholder. */
  placeholder?: string;
  /** Override the debounce delay in ms. Default: 300. */
  delay?: number;
  /** Disable the global `/` keyboard shortcut. */
  isShortcutDisabled?: boolean;
  /** Show a clear (X) button on the trailing side when the input has a value. */
  isClearable?: boolean;
  className?: string;
  ariaLabel?: string;
}

/**
 * Search box with built-in debounce and a global `/` keyboard shortcut to
 * focus. Keeps internal state and only fires `onChange` after the user
 * stops typing.
 */
export default function SearchInput({
  initialValue = "",
  value: controlledValue,
  onChange,
  placeholder,
  delay = 300,
  isShortcutDisabled = false,
  isClearable = false,
  className = "",
  ariaLabel,
}: SearchInputProps) {
  const { t } = useTranslation(['common', 'http']);
  const isControlled = controlledValue !== undefined;
  const [internal, setInternal] = useState(initialValue);
  const value = isControlled ? controlledValue : internal;
  const debounced = useDebounce(internal, delay);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isControlled) return;
    onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced, isControlled]);

  useEffect(() => {
    if (isShortcutDisabled) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isShortcutDisabled]);

  const handleClear = () => {
    if (isControlled) {
      onChange("");
    } else {
      setInternal("");
    }
    inputRef.current?.focus();
  };

  const isShowingClear = isClearable && value.length > 0;
  // Hide native webkit search clear button so our custom X is the only one.
  const noNativeClear =
    "[&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-decoration]:appearance-none";

  const input = (
    <input
      ref={inputRef}
      type="search"
      value={value}
      onChange={(e) => {
        const next = e.target.value;
        if (isControlled) {
          onChange(next);
        } else {
          setInternal(next);
        }
      }}
      placeholder={placeholder ?? t("common:searchPlaceholder")}
      aria-label={ariaLabel ?? t("common:search")}
      className={`${INPUT_CLS} ${noNativeClear} ${isShowingClear ? "pe-9" : ""} ${className}`}
    />
  );

  if (!isClearable) return input;

  return (
    <div className="relative">
      {input}
      {isShowingClear && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleClear}
          aria-label={t("common:clear")}
          className="absolute inset-y-0 end-2 my-auto inline-flex size-6 items-center justify-center rounded-full text-white/45 transition hover:bg-white/8 hover:text-white/85"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className="size-3.5"
            aria-hidden="true"
          >
            <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06L6.94 8l-4.72 4.72a.75.75 0 1 0 1.06 1.06L8 9.06l4.72 4.72a.75.75 0 1 0 1.06-1.06L9.06 8l4.72-4.72a.75.75 0 0 0-1.06-1.06L8 6.94 3.28 2.22Z" />
          </svg>
        </button>
      )}
    </div>
  );
}
