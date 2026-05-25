"use client";

import {
  KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { Label } from "../Label/Label";
import styles from "./Select.module.css";

export type SelectOption = {
  value: string;
  label: string;
};

export type SelectProps = {
  label: string;
  options: SelectOption[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  helperText?: string;
  error?: string;
  success?: boolean;
  required?: boolean;
  disabled?: boolean;
  id?: string;
  name?: string;
  className?: string;
};

const SEARCH_THRESHOLD = 10;

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      className={styles.optionCheck}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3.5 8l3 3 6-6" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg
      className={styles.errorIcon}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 5v3.5M8 11v.5" />
    </svg>
  );
}

export function Select({
  label,
  options,
  value,
  onChange,
  placeholder = "Selecione...",
  helperText,
  error,
  success,
  required,
  disabled,
  id: idProp,
  name,
  className,
}: SelectProps) {
  const reactId = useId();
  const id = idProp ?? reactId;
  const listboxId = `${id}-listbox`;
  const helperId = helperText ? `${id}-helper` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState<number>(-1);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);

  const showSearch = options.length > SEARCH_THRESHOLD;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
        setHighlighted(-1);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (open && showSearch) {
      const t = setTimeout(() => searchRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [open, showSearch]);

  function openDropdown() {
    if (disabled || open) return;
    const initial = Math.max(
      0,
      options.findIndex((o) => o.value === value),
    );
    setHighlighted(initial);
    setOpen(true);
  }

  function closeDropdown() {
    setOpen(false);
    setQuery("");
    setHighlighted(-1);
  }

  function pick(option: SelectOption) {
    onChange?.(option.value);
    closeDropdown();
    triggerRef.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLElement>) {
    if (disabled) return;

    if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();
      closeDropdown();
      triggerRef.current?.focus();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        openDropdown();
        return;
      }
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        openDropdown();
        return;
      }
      setHighlighted((h) => Math.max(h - 1, 0));
      return;
    }

    if (e.key === "Enter") {
      if (!open) {
        e.preventDefault();
        openDropdown();
        return;
      }
      if (highlighted >= 0 && highlighted < filtered.length) {
        e.preventDefault();
        pick(filtered[highlighted]);
      }
      return;
    }

    if (e.key === " " && !open) {
      e.preventDefault();
      openDropdown();
    }
  }

  const stateClass = error ? styles.error : success ? styles.success : "";

  return (
    <div
      className={`${styles.field} ${className ?? ""}`}
      ref={containerRef}
      onKeyDown={onKeyDown}
    >
      <Label htmlFor={id} required={required}>
        {label}
      </Label>

      <button
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-invalid={!!error || undefined}
        aria-describedby={helperId}
        aria-errormessage={errorId}
        disabled={disabled}
        onClick={() => (open ? closeDropdown() : openDropdown())}
        className={`${styles.trigger} ${stateClass} ${
          open ? styles.triggerOpen : ""
        }`}
      >
        <span className={selected ? "" : styles.triggerPlaceholder}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronIcon open={open} />
      </button>

      {name && <input type="hidden" name={name} value={value ?? ""} />}

      {open && (
        <div className={styles.dropdown}>
          {showSearch && (
            <div className={styles.searchWrap}>
              <input
                ref={searchRef}
                type="text"
                className={styles.search}
                placeholder="Buscar..."
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setHighlighted(0);
                }}
                aria-label="Buscar opções"
              />
            </div>
          )}
          <ul
            id={listboxId}
            role="listbox"
            aria-label={label}
            className={styles.options}
          >
            {filtered.length === 0 ? (
              <li className={styles.empty}>Nenhuma opção encontrada</li>
            ) : (
              filtered.map((opt, idx) => {
                const isSelected = opt.value === value;
                const isHighlighted = idx === highlighted;
                return (
                  <li
                    key={opt.value}
                    role="option"
                    aria-selected={isSelected}
                    className={`${styles.option} ${
                      isHighlighted ? styles.optionHighlighted : ""
                    } ${isSelected ? styles.optionSelected : ""}`}
                    onMouseEnter={() => setHighlighted(idx)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(opt);
                    }}
                  >
                    <span>{opt.label}</span>
                    {isSelected && <CheckIcon />}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}

      {helperText && !error && (
        <span id={helperId} className={styles.helper}>
          {helperText}
        </span>
      )}

      {error && (
        <span id={errorId} className={styles.errorMessage} role="alert">
          <ErrorIcon />
          {error}
        </span>
      )}
    </div>
  );
}
