"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { Label } from "@/app/components/ui/Label/Label";
import { ErrorIcon } from "@/app/components/icons";
import type { AcaoPT } from "@/app/lib/atividades";

/** Rótulo exibido para uma ação: "1.2 — Descrição da ação". */
export function acaoLabel(acao: AcaoPT): string {
  return `${acao.numero} — ${acao.descricao}`;
}

function normalize(text: string): string {
  return text
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

/**
 * Filtra as ações pelo termo digitado, casando contra número e descrição.
 * Ignora acentos e caixa; termos separados por espaço precisam casar todos
 * ("1.2 poço" encontra "1.2 — Construção de poços"). Exportada para teste.
 */
export function filterAcoes(acoes: AcaoPT[], query: string): AcaoPT[] {
  const termos = normalize(query).split(/\s+/).filter(Boolean);
  if (termos.length === 0) return acoes;
  return acoes.filter((acao) => {
    const alvo = normalize(`${acao.numero} ${acao.descricao}`);
    return termos.every((t) => alvo.includes(t));
  });
}

const MAX_VISIVEIS = 50;

type Props = {
  acoes: AcaoPT[];
  value: AcaoPT | null;
  onChange: (acao: AcaoPT | null) => void;
  loading?: boolean;
  error?: string;
  id: string;
  required?: boolean;
};

/**
 * Combobox de Ação do PT com busca em memória.
 *
 * A busca é client-side porque o WorkPlanAcaoViewSet não expõe filtro de texto
 * — a lista inteira é carregada uma vez pelo formulário e filtrada aqui.
 */
export function AcaoCombobox({
  acoes,
  value,
  onChange,
  loading,
  error,
  id,
  required,
}: Props) {
  const listboxId = `${id}-listbox`;
  const errorId = error ? `${id}-error` : undefined;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtradas = useMemo(
    () => filterAcoes(acoes, query).slice(0, MAX_VISIVEIS),
    [acoes, query],
  );

  const totalFiltradas = useMemo(
    () => filterAcoes(acoes, query).length,
    [acoes, query],
  );

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

  function pick(acao: AcaoPT) {
    onChange(acao);
    setOpen(false);
    setQuery("");
  }

  function clear() {
    onChange(null);
    setQuery("");
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setHighlighted(0);
        return;
      }
      setHighlighted((h) => Math.min(h + 1, filtradas.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
      return;
    }
    if (e.key === "Enter" && open) {
      const escolhida = filtradas[highlighted];
      if (escolhida) {
        e.preventDefault();
        pick(escolhida);
      }
      return;
    }
    if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
    }
  }

  const borderCls = error ? "border-error-text" : "border-border";

  // Estado selecionado: mostra a ação escolhida com botão de limpar.
  if (value) {
    return (
      <div className="flex flex-col gap-1" ref={rootRef}>
        <Label htmlFor={id} required={required}>
          Ação do PT
        </Label>
        <div
          className={`flex min-h-9 items-center gap-2 rounded-md border bg-surface px-3 py-1 text-sm ${borderCls}`}
        >
          <span className="flex-1 text-text">{acaoLabel(value)}</span>
          <button
            id={id}
            type="button"
            aria-label={`Remover ação ${acaoLabel(value)}`}
            onClick={clear}
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-text-muted hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        {error && <FieldError id={errorId}>{error}</FieldError>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1" ref={rootRef}>
      <Label htmlFor={id} required={required}>
        Ação do PT
      </Label>

      <div className="relative">
        <div
          className={`flex h-9 items-center gap-2 rounded-md border bg-surface px-3 text-sm text-text focus-within:border-2 focus-within:border-primary ${borderCls}`}
        >
          <Search className="h-3.5 w-3.5 shrink-0 text-text-muted" />
          <input
            ref={inputRef}
            id={id}
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-invalid={!!error || undefined}
            aria-errormessage={errorId}
            autoComplete="off"
            value={query}
            disabled={loading}
            placeholder={
              loading ? "Carregando atividades…" : "Busque por número ou descrição"
            }
            onChange={(e) => {
              setQuery(e.target.value);
              setHighlighted(0);
              if (!open) setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            className="h-full flex-1 bg-transparent outline-none placeholder:text-text-muted disabled:cursor-not-allowed"
          />
          <ChevronDown className="h-4 w-4 shrink-0 text-text-muted" />
        </div>

        {open && !loading && (
          <ul
            id={listboxId}
            role="listbox"
            aria-label="Ações do Plano de Trabalho"
            className="absolute left-0 right-0 top-full z-30 mt-1 max-h-64 list-none overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
          >
            {filtradas.length === 0 ? (
              <li className="px-3 py-3 text-sm text-text-muted">
                Nenhuma ação encontrada.
              </li>
            ) : (
              <>
                {filtradas.map((acao, idx) => (
                  <li
                    key={acao.id}
                    role="option"
                    aria-selected={idx === highlighted}
                    onMouseEnter={() => setHighlighted(idx)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(acao);
                    }}
                    className={`cursor-pointer px-3 py-2 text-sm text-text ${
                      idx === highlighted ? "bg-surface-muted" : ""
                    }`}
                  >
                    <span className="font-medium tabular-nums">{acao.numero}</span>
                    <span className="text-text-muted"> — </span>
                    <span>{acao.descricao}</span>
                  </li>
                ))}
                {totalFiltradas > filtradas.length && (
                  <li className="px-3 py-2 text-xs text-text-muted">
                    Mostrando {filtradas.length} de {totalFiltradas}. Refine a
                    busca.
                  </li>
                )}
              </>
            )}
          </ul>
        )}
      </div>

      {error && <FieldError id={errorId}>{error}</FieldError>}
    </div>
  );
}

function FieldError({
  id,
  children,
}: {
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      id={id}
      role="alert"
      className="inline-flex items-center gap-1 text-xs leading-[1.4] text-error-text"
    >
      <ErrorIcon />
      {children}
    </span>
  );
}
