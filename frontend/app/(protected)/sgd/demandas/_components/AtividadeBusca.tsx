"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Label } from "@/app/components/ui/Label/Label";
import { ApiError } from "@/app/lib/api";
import { badgeStatusFor } from "@/app/lib/atividades";
import { formatDate } from "@/app/lib/datetime";
import {
  buscarAtividadesElegiveis,
  type AtividadeElegivel,
} from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";

const DEBOUNCE_MS = 300;

type AtividadeBuscaProps = {
  /** Usuário logado — a busca cobre só as atividades dele (RF01). */
  tecnicoId: string;
  value: AtividadeElegivel | null;
  onChange: (atividade: AtividadeElegivel | null) => void;
  error?: string;
};

/**
 * Campo "Atividade" com busca (#294, caminho alternativo pelo SGD).
 *
 * A busca é feita no SERVIDOR a cada digitação (com debounce): a lista de
 * atividades é paginada, e filtrar só o que já veio esconderia as demais.
 * Enquanto o `ActivityFilter` não aceitar `q`, o texto digitado não estreita o
 * resultado (docs/pendencias-backend-sprint-10.md, item 9).
 *
 * Combobox WAI-ARIA: ↑/↓ percorrem as opções, Enter escolhe, Esc fecha.
 */
export function AtividadeBusca({
  tecnicoId,
  value,
  onChange,
  error,
}: AtividadeBuscaProps) {
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
    queryKey: qk.atividadesElegiveis(tecnicoId, busca),
    queryFn: ({ signal }) =>
      buscarAtividadesElegiveis({ tecnicoId, busca }, signal),
    enabled: aberto && !!tecnicoId,
    staleTime: 30_000,
  });
  const opcoes = data ?? [];

  function escolher(atividade: AtividadeElegivel) {
    onChange(atividade);
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
        <Label htmlFor={inputId}>Atividade</Label>
        <div
          className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-3 py-2 text-sm"
          data-testid="atividade-escolhida"
        >
          <span className="min-w-0 truncate">
            {value.titulo}
            <span className="ml-2 text-xs text-text-muted">
              {value.municipio.nome} · {formatDate(value.data_inicio)}
            </span>
          </span>
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
        </div>
      </div>
    );
  }

  const mensagemErro =
    erroBusca instanceof ApiError
      ? erroBusca.message
      : erroBusca
        ? "Não foi possível buscar as atividades."
        : null;
  const ativo = destacado >= 0 && opcoes[destacado];

  return (
    <div className="relative flex flex-col gap-1.5">
      <Label htmlFor={inputId} required>
        Atividade
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
          aria-activedescendant={ativo ? `${listboxId}-${ativo.id}` : undefined}
          aria-invalid={!!error || undefined}
          aria-describedby={error ? errorId : undefined}
          placeholder="Buscar entre as suas atividades planejadas ou agendadas…"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            setAberto(true);
            setDestacado(-1);
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 150)}
          onKeyDown={onKeyDown}
          className={`h-9 w-full rounded-md border bg-surface pl-9 pr-9 text-sm text-text outline-none transition focus-visible:border-primary focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] ${
            error ? "border-error-text" : "border-border"
          }`}
          data-testid="atividade-busca"
        />
        {isFetching && (
          <Spinner className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-text-muted" />
        )}
      </div>

      {aberto && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Atividades encontradas"
          className="absolute top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
        >
          {mensagemErro ? (
            <li className="px-3 py-2 text-sm text-error-text">{mensagemErro}</li>
          ) : opcoes.length === 0 && !isFetching ? (
            <li className="px-3 py-2 text-sm text-text-muted">
              Nenhuma atividade planejada ou agendada encontrada.
            </li>
          ) : (
            opcoes.map((a, i) => (
              <li
                key={a.id}
                id={`${listboxId}-${a.id}`}
                role="option"
                aria-selected={i === destacado}
                // mousedown antes do blur do input: o clique chega a escolher.
                onMouseDown={(e) => {
                  e.preventDefault();
                  escolher(a);
                }}
                onMouseEnter={() => setDestacado(i)}
                className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm ${
                  i === destacado ? "bg-primary/10" : ""
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-text">{a.titulo}</span>
                  <span className="block text-xs text-text-muted">
                    {a.municipio.nome} · {formatDate(a.data_inicio)}
                  </span>
                </span>
                <Badge status={badgeStatusFor(a.status)} label={a.status_display} />
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
