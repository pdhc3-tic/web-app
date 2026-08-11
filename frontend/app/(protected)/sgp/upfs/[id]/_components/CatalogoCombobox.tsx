"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { Label } from "@/app/components/ui/Label/Label";
import type { CatalogoItem } from "@/app/lib/producao";

type Props = {
  label: string;
  required?: boolean;
  value: CatalogoItem | null;
  onChange: (v: CatalogoItem | null) => void;
  search: (q: string, signal?: AbortSignal) => Promise<CatalogoItem[]>;
  placeholder?: string;
  error?: string;
};

export function CatalogoCombobox({
  label,
  required,
  value,
  onChange,
  search,
  placeholder,
  error,
}: Props) {
  const inputId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<CatalogoItem[]>([]);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const controller = new AbortController();
    const t = setTimeout(() => {
      search(query, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) setItems(data);
        })
        .catch(() => {})
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 300);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [open, query, search]);

  useEffect(() => {
    if (!open) return;
    function handle(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  function pick(item: CatalogoItem) {
    onChange(item);
    setOpen(false);
    setQuery("");
  }

  const borderCls = error ? "border-error-text" : "border-border";

  return (
    <div className="flex flex-col gap-1" ref={rootRef}>
      <Label htmlFor={inputId} required={required}>{label}</Label>

      {value ? (
        <div className={`flex h-9 items-center gap-2 rounded-md border bg-surface px-3 text-sm ${borderCls}`}>
          <span className="truncate text-text">{value.nome}</span>
          <CategoriaChip>{value.categoria}</CategoriaChip>
          <button
            type="button"
            aria-label={`Remover ${value.nome}`}
            onClick={() => onChange(null)}
            className="ml-auto inline-flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <div className={`flex h-9 items-center gap-2 rounded-md border bg-surface px-3 text-sm text-text focus-within:border-2 focus-within:border-primary ${borderCls}`}>
            <Search className="h-3.5 w-3.5 text-text-muted" />
            <input
              id={inputId}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (!open) setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              placeholder={placeholder}
              className="h-full flex-1 bg-transparent outline-none placeholder:text-text-muted"
              aria-invalid={!!error || undefined}
            />
            <ChevronDown className="h-4 w-4 text-text-muted" />
          </div>

          {open && (
            <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-md border border-border bg-surface shadow-lg">
              {loading ? (
                <div className="px-3 py-3 text-sm text-text-muted">Buscando...</div>
              ) : items.length === 0 ? (
                <div className="px-3 py-3 text-sm text-text-muted">Nenhum resultado.</div>
              ) : (
                <ul>
                  {items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => pick(item)}
                        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-surface-muted"
                      >
                        <span className="truncate text-text">{item.nome}</span>
                        <CategoriaChip>{item.categoria}</CategoriaChip>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {error && <span className="text-xs text-error-text">{error}</span>}
    </div>
  );
}

function CategoriaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-border bg-surface-muted px-1.5 py-0.5 text-2xs text-text-muted">
      {children}
    </span>
  );
}
