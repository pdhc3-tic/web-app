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
import {
  ChevronDownIcon,
  CheckIcon,
  ErrorIcon,
} from "@/app/components/icons";

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

const triggerBase =
  "w-full h-9 px-3 flex items-center justify-between gap-2 text-sm text-text bg-surface border border-border rounded-md outline-none cursor-pointer text-left transition duration-[120ms] enabled:hover:border-text-muted focus-visible:border-2 focus-visible:border-primary focus-visible:px-[calc(var(--space-3)-1px)] focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] disabled:bg-surface-muted disabled:text-text-muted disabled:cursor-not-allowed disabled:opacity-70";

const triggerOpenClass =
  "border-2 border-primary px-[calc(var(--space-3)-1px)] shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)]";

const triggerError =
  "border-error-text focus-visible:border-error-text focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]";

const triggerErrorOpenOverride =
  "border-error-text shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]";

const triggerSuccess =
  "border-success-text focus-visible:border-success-text";

const triggerSuccessOpenOverride = "border-success-text";

function buildTriggerClass(
  open: boolean,
  error: boolean,
  success: boolean,
): string {
  const parts: string[] = [triggerBase];
  if (open) parts.push(triggerOpenClass);
  if (error) {
    parts.push(triggerError);
    if (open) parts.push(triggerErrorOpenOverride);
  } else if (success) {
    parts.push(triggerSuccess);
    if (open) parts.push(triggerSuccessOpenOverride);
  }
  return parts.join(" ");
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

  return (
    <div
      className={`relative flex flex-col gap-1 ${className ?? ""}`}
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
        className={buildTriggerClass(open, !!error, !!success)}
      >
        <span className={selected ? "" : "text-text-muted"}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDownIcon
          className={`w-3.5 h-3.5 shrink-0 text-text-muted transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {name && <input type="hidden" name={name} value={value ?? ""} />}

      {open && (
        <div className="absolute top-[calc(100%+var(--space-1))] left-0 right-0 z-30 flex flex-col max-h-[280px] bg-surface border border-border rounded-md shadow-md overflow-hidden">
          {showSearch && (
            <div className="p-2 border-b border-border bg-surface">
              <input
                ref={searchRef}
                type="text"
                className="w-full h-[30px] px-2 text-label text-text bg-surface-muted border border-border rounded-sm outline-none focus:border-primary focus:bg-surface"
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
            className="list-none m-0 py-1 px-0 overflow-y-auto flex-1"
          >
            {filtered.length === 0 ? (
              <li className="p-3 text-label text-text-muted text-center">
                Nenhuma opção encontrada
              </li>
            ) : (
              filtered.map((opt, idx) => {
                const isSelected = opt.value === value;
                const isHighlighted = idx === highlighted;
                const optionClass = [
                  "py-2 px-3 text-sm text-text cursor-pointer flex items-center gap-2",
                  isHighlighted && "bg-surface-muted",
                  isSelected && "text-primary font-medium",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <li
                    key={opt.value}
                    role="option"
                    aria-selected={isSelected}
                    className={optionClass}
                    onMouseEnter={() => setHighlighted(idx)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(opt);
                    }}
                  >
                    <span>{opt.label}</span>
                    {isSelected && (
                      <CheckIcon className="w-3.5 h-3.5 ml-auto shrink-0" />
                    )}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}

      {helperText && !error && (
        <span id={helperId} className="text-xs text-text-muted leading-[1.4]">
          {helperText}
        </span>
      )}

      {error && (
        <span
          id={errorId}
          className="inline-flex items-center gap-1 text-xs text-error-text leading-[1.4]"
          role="alert"
        >
          <ErrorIcon />
          {error}
        </span>
      )}
    </div>
  );
}
