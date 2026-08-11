"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { Label } from "@/app/components/ui/Label/Label";
import type { TecnicoOption } from "@/app/lib/atividades";

type Props = {
  id: string;
  /** Técnicos disponíveis; vazio quando o backend nega a listagem de usuários. */
  opcoes: TecnicoOption[];
  value: number[];
  onChange: (ids: number[]) => void;
  loading?: boolean;
  /** Exclui o técnico responsável da lista para não duplicar. */
  excluirId?: number;
};

/** Multi-seleção de técnicos para a equipe adicional da atividade. */
export function EquipeAdicionalPicker({
  id,
  opcoes,
  value,
  onChange,
  loading,
  excluirId,
}: Props) {
  const listboxId = `${id}-listbox`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  const disponiveis = useMemo(
    () => opcoes.filter((o) => o.id !== excluirId),
    [opcoes, excluirId],
  );

  const filtradas = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("pt-BR");
    if (!q) return disponiveis;
    return disponiveis.filter((o) => o.nome.toLocaleLowerCase("pt-BR").includes(q));
  }, [disponiveis, query]);

  const selecionados = useMemo(
    () => disponiveis.filter((o) => value.includes(o.id)),
    [disponiveis, value],
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

  function toggle(tecnicoId: number) {
    onChange(
      value.includes(tecnicoId)
        ? value.filter((v) => v !== tecnicoId)
        : [...value, tecnicoId],
    );
  }

  const indisponivel = !loading && opcoes.length === 0;

  return (
    <div className="flex flex-col gap-1" ref={rootRef}>
      <Label htmlFor={id}>Equipe adicional</Label>

      <div className="relative">
        <button
          id={id}
          type="button"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listboxId}
          disabled={loading || indisponivel}
          onClick={() => setOpen((o) => !o)}
          className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 text-left text-sm text-text outline-none transition enabled:hover:border-text-muted focus-visible:border-2 focus-visible:border-primary disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted disabled:opacity-70"
        >
          <span className={selecionados.length > 0 ? "" : "text-text-muted"}>
            {loading
              ? "Carregando atividades…"
              : indisponivel
                ? "Indisponível para o seu perfil"
                : selecionados.length > 0
                  ? `${selecionados.length} selecionado(s)`
                  : "Selecione os técnicos"}
          </span>
          <ChevronDown
            className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>

        {open && (
          <div className="absolute left-0 right-0 top-full z-30 mt-1 flex max-h-72 flex-col overflow-hidden rounded-md border border-border bg-surface shadow-lg">
            <div className="border-b border-border p-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar técnico..."
                aria-label="Buscar técnico"
                className="h-7.5 w-full rounded-sm border border-border bg-surface-muted px-2 text-label text-text outline-none focus:border-primary focus:bg-surface"
              />
            </div>
            <ul
              id={listboxId}
              role="listbox"
              aria-multiselectable="true"
              aria-label="Equipe adicional"
              className="list-none overflow-y-auto py-1"
            >
              {filtradas.length === 0 ? (
                <li className="px-3 py-3 text-sm text-text-muted">
                  Nenhum técnico encontrado.
                </li>
              ) : (
                filtradas.map((o) => {
                  const marcado = value.includes(o.id);
                  return (
                    <li key={o.id} role="option" aria-selected={marcado}>
                      <label className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-text hover:bg-surface-muted">
                        <input
                          type="checkbox"
                          checked={marcado}
                          onChange={() => toggle(o.id)}
                          className="h-4 w-4 shrink-0 accent-(--color-primary)"
                        />
                        <span className="truncate">{o.nome}</span>
                      </label>
                    </li>
                  );
                })
              )}
            </ul>
          </div>
        )}
      </div>

      {selecionados.length > 0 && (
        <ul className="mt-1 flex list-none flex-wrap gap-2">
          {selecionados.map((o) => (
            <li
              key={o.id}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted py-1 pl-3 pr-1 text-xs text-text"
            >
              <span>{o.nome}</span>
              <button
                type="button"
                aria-label={`Remover ${o.nome} da equipe`}
                onClick={() => toggle(o.id)}
                className="inline-flex h-5 w-5 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {indisponivel && (
        <span className="text-xs text-text-muted">
          A listagem de usuários é restrita no backend; peça ao Super Admin para
          liberar o endpoint para o seu perfil.
        </span>
      )}
    </div>
  );
}
