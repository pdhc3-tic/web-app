"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Label } from "../Label/Label";

const DEBOUNCE_MS = 300;

export type SearchSelectOption<T = unknown> = {
  value: string;
  label: string;
  /** Linha secundária da opção (ex.: município · data). */
  description?: string;
  /** O item original, devolvido em `onChange`. */
  item: T;
};

export type SearchSelectProps<T> = {
  label: string;
  /** Opção escolhida; `null` mostra o campo de busca. */
  value: SearchSelectOption<T> | null;
  onChange: (option: SearchSelectOption<T> | null) => void;
  /** Busca no servidor pelo texto digitado (já com debounce). */
  search: (text: string, signal: AbortSignal) => Promise<SearchSelectOption<T>[]>;
  /** Chave de cache da busca para um texto — vinda de `queryKeys.ts`. */
  queryKey: (text: string) => QueryKey;
  placeholder?: string;
  /** Mensagem quando a busca não traz nada. */
  emptyText?: string;
  /** Conteúdo extra à direita de cada opção (ex.: um Badge de status). */
  renderAside?: (option: SearchSelectOption<T>) => ReactNode;
  required?: boolean;
  error?: string;
  disabled?: boolean;
  "data-testid"?: string;
};

const campoBase =
  "h-9 w-full rounded-md border bg-surface pl-9 pr-9 text-sm text-text outline-none transition duration-[120ms] hover:border-text-muted focus-visible:border-2 focus-visible:border-primary focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted";

/**
 * Select pesquisável com busca no SERVIDOR — para listas grandes e paginadas,
 * em que filtrar só o que já veio (como faz o `Select` acima de 10 opções)
 * esconderia o resto.
 *
 * Mesma aparência do `Select` (rótulo, obrigatório, erro). Combobox WAI-ARIA:
 * ↑/↓ percorrem as opções, Enter escolhe, Esc fecha. Escolhida a opção, o
 * campo mostra o valor com "Trocar".
 */
export function SearchSelect<T>({
  label,
  value,
  onChange,
  search,
  queryKey,
  placeholder = "Digite para buscar…",
  emptyText = "Nenhum resultado.",
  renderAside,
  required,
  error,
  disabled,
  "data-testid": testId,
}: SearchSelectProps<T>) {
  const baseId = useId();
  const inputId = `${baseId}-input`;
  const listboxId = `${baseId}-listbox`;
  const errorId = `${baseId}-error`;

  const [texto, setTexto] = useState("");
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState(false);
  const [destacado, setDestacado] = useState(-1);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setBusca(texto), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [texto]);

  const { data, isFetching, error: erroBusca } = useQuery({
    queryKey: queryKey(busca),
    queryFn: ({ signal }) => search(busca, signal),
    enabled: aberto && !disabled,
    staleTime: 30_000,
  });
  const opcoes = data ?? [];

  function escolher(opcao: SearchSelectOption<T>) {
    onChange(opcao);
    setAberto(false);
    setTexto("");
    setDestacado(-1);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAberto(true);
      setDestacado((d) => Math.min(d + 1, opcoes.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setDestacado((d) => Math.max(d - 1, 0));
    } else if (e.key === "Enter") {
      if (aberto && destacado >= 0 && opcoes[destacado]) {
        e.preventDefault();
        escolher(opcoes[destacado]);
      }
    } else if (e.key === "Escape") {
      setAberto(false);
    }
  }

  if (value) {
    return (
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={inputId} required={required}>
          {label}
        </Label>
        <div
          className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-3 py-2 text-sm"
          data-testid={testId ? `${testId}-escolhida` : undefined}
        >
          <span className="min-w-0 truncate">
            {value.label}
            {value.description && (
              <span className="ml-2 text-xs text-text-muted">{value.description}</span>
            )}
          </span>
          {!disabled && (
            <button
              id={inputId}
              type="button"
              onClick={() => {
                onChange(null);
                requestAnimationFrame(() => inputRef.current?.focus());
              }}
              className="inline-flex shrink-0 items-center gap-1 rounded text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              Trocar
            </button>
          )}
        </div>
      </div>
    );
  }

  const ativo = destacado >= 0 ? opcoes[destacado] : undefined;
  const mensagemErro = erroBusca
    ? erroBusca instanceof Error && erroBusca.message
      ? erroBusca.message
      : "Não foi possível buscar."
    : null;

  return (
    <div className="relative flex flex-col gap-1.5">
      <Label htmlFor={inputId} required={required}>
        {label}
      </Label>
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-expanded={aberto}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={ativo ? `${listboxId}-${ativo.value}` : undefined}
          aria-invalid={!!error || undefined}
          aria-describedby={error ? errorId : undefined}
          placeholder={placeholder}
          value={texto}
          disabled={disabled}
          onChange={(e) => {
            setTexto(e.target.value);
            setAberto(true);
            setDestacado(-1);
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          onKeyDown={onKeyDown}
          className={`${campoBase} ${error ? "border-error-text" : "border-border"}`}
          data-testid={testId}
        />
        {isFetching && (
          <Spinner className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-text-muted" />
        )}
      </div>

      {aberto && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label={label}
          className="absolute top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
        >
          {mensagemErro ? (
            <li className="px-3 py-2 text-sm text-error-text">{mensagemErro}</li>
          ) : opcoes.length === 0 && !isFetching ? (
            <li className="px-3 py-2 text-sm text-text-muted">{emptyText}</li>
          ) : (
            opcoes.map((o, i) => (
              <li
                key={o.value}
                id={`${listboxId}-${o.value}`}
                role="option"
                aria-selected={i === destacado}
                // mousedown antes do blur do input: o clique chega a escolher.
                onMouseDown={(e) => {
                  e.preventDefault();
                  escolher(o);
                }}
                onMouseEnter={() => setDestacado(i)}
                className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm ${
                  i === destacado ? "bg-primary/10" : ""
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-text">{o.label}</span>
                  {o.description && (
                    <span className="block text-xs text-text-muted">{o.description}</span>
                  )}
                </span>
                {renderAside?.(o)}
              </li>
            ))
          )}
        </ul>
      )}

      {error && (
        <p id={errorId} className="text-xs text-error-text">
          {error}
        </p>
      )}
    </div>
  );
}
