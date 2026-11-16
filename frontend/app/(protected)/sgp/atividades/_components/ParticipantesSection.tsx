"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { Label } from "@/app/components/ui/Label/Label";
import { ErrorIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { listUfpas, type UfpaListItem } from "@/app/lib/ufpas";
import { listMembros, type MembroListItem } from "@/app/lib/membros";
import {
  PENDING_UFPA_ID,
  fieldId,
  type MembroRef,
  type UfpaRef,
} from "./formModel";

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_LIMIT = 10;

type Props = {
  ufpas: UfpaRef[];
  membros: MembroRef[];
  onChange: (patch: {
    ufpas_participantes?: UfpaRef[];
    membros_participantes?: MembroRef[];
  }) => void;
  errors: Record<string, string>;
};

/**
 * Seleção de UFPAs e membros participantes.
 *
 * A busca de UFPA usa o mesmo filtro `q` do módulo Famílias/UFPAs (nome do titular
 * ou CPF). Os membros oferecidos são os das UFPAs já selecionadas — remover uma
 * UFPA remove junto os membros dela. A contagem de participantes é derivada dos
 * membros e nunca editável.
 */
export function ParticipantesSection({
  ufpas,
  membros,
  onChange,
  errors,
}: Props) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [resultados, setResultados] = useState<UfpaListItem[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);

  const [membrosPorUfpa, setMembrosPorUfpa] = useState<
    Record<number, MembroListItem[]>
  >({});
  const [carregandoMembros, setCarregandoMembros] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Lidos dentro do efeito de carga dos membros sem entrar nas dependências —
  // incluí-los reiniciaria o fetch a cada seleção de membro.
  const membrosRef = useRef(membros);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    membrosRef.current = membros;
    onChangeRef.current = onChange;
  });

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  // Busca de UFPAs por nome do titular ou CPF.
  useEffect(() => {
    const termo = debounced.trim();
    if (termo === "") {
      // Descarta o resultado anterior para não piscar itens obsoletos quando o
      // usuário limpa a busca. Mesmo padrão do CatalogoCombobox do módulo UFPA.
      /* eslint-disable react-hooks/set-state-in-effect */
      setResultados([]);
      setBuscando(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      return;
    }
    const controller = new AbortController();
    setBuscando(true);
    setErroBusca(null);
    listUfpas(
      { limit: SEARCH_LIMIT, offset: 0, search: termo, status: "ativas" },
      controller.signal,
    )
      .then((page) => {
        if (controller.signal.aborted) return;
        setResultados(page.results);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setErroBusca("Não foi possível buscar UFPAs. Tente novamente.");
        setResultados([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBuscando(false);
      });
    return () => controller.abort();
  }, [debounced]);

  // Carrega os membros de cada UFPA selecionada que ainda não está em cache.
  useEffect(() => {
    const pendentes = ufpas.filter((u) => !(u.id in membrosPorUfpa));
    if (pendentes.length === 0) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregandoMembros(true);
    Promise.all(
      pendentes.map((u) =>
        listMembros(u.id, controller.signal)
          .then((lista) => [u.id, lista] as const)
          .catch(() => [u.id, [] as MembroListItem[]] as const),
      ),
    )
      .then((pares) => {
        if (controller.signal.aborted) return;
        setMembrosPorUfpa((prev) => {
          const next = { ...prev };
          for (const [ufpaId, lista] of pares) next[ufpaId] = lista;
          return next;
        });

        // Prefill de edição: os membros já selecionados chegam sem nome e sem
        // UFPA (só o id). Agora que a lista de cada UFPA carregou, dá para
        // completá-los — sem isso, "Desmarcar todos" não os alcançaria.
        const pendentesSelecionados = membrosRef.current.some(
          (m) => m.ufpaId === PENDING_UFPA_ID,
        );
        if (!pendentesSelecionados) return;

        const porId = new Map<number, { nome: string; ufpaId: number }>();
        for (const [ufpaId, lista] of pares) {
          for (const m of lista) porId.set(m.id, { nome: m.nome_completo, ufpaId });
        }
        onChangeRef.current({
          membros_participantes: membrosRef.current.map((m) => {
            if (m.ufpaId !== PENDING_UFPA_ID) return m;
            const resolvido = porId.get(m.id);
            return resolvido ? { id: m.id, ...resolvido } : m;
          }),
        });
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregandoMembros(false);
      });

    return () => controller.abort();
  }, [ufpas, membrosPorUfpa]);

  const adicionarUfpa = useCallback(
    (item: UfpaListItem) => {
      if (ufpas.some((u) => u.id === item.id)) return;
      onChange({
        ufpas_participantes: [
          ...ufpas,
          { id: item.id, nome: item.nome_titular, cpf: item.cpf },
        ],
      });
      setQuery("");
      setResultados([]);
      searchInputRef.current?.focus();
    },
    [ufpas, onChange],
  );

  const removerUfpa = useCallback(
    (ufpaId: number) => {
      onChange({
        ufpas_participantes: ufpas.filter((u) => u.id !== ufpaId),
        // Membros da UFPA removida saem junto da seleção.
        membros_participantes: membros.filter((m) => m.ufpaId !== ufpaId),
      });
    },
    [ufpas, membros, onChange],
  );

  const toggleMembro = useCallback(
    (membro: MembroListItem, ufpaId: number, marcado: boolean) => {
      onChange({
        membros_participantes: marcado
          ? [
              ...membros,
              { id: membro.id, nome: membro.nome_completo, ufpaId },
            ]
          : membros.filter((m) => m.id !== membro.id),
      });
    },
    [membros, onChange],
  );

  const toggleTodosDaUfpa = useCallback(
    (ufpaId: number, marcar: boolean) => {
      const lista = membrosPorUfpa[ufpaId] ?? [];
      if (marcar) {
        const jaSelecionados = new Set(membros.map((m) => m.id));
        const novos = lista
          .filter((m) => !jaSelecionados.has(m.id))
          .map((m) => ({ id: m.id, nome: m.nome_completo, ufpaId }));
        onChange({ membros_participantes: [...membros, ...novos] });
      } else {
        onChange({
          membros_participantes: membros.filter((m) => m.ufpaId !== ufpaId),
        });
      }
    },
    [membrosPorUfpa, membros, onChange],
  );

  const selecionados = new Set(membros.map((m) => m.id));

  return (
    <div className="flex flex-col gap-4">
      {/* ── Busca de UFPAs ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        <Label htmlFor={fieldId("ufpas_participantes")}>
          UFPAs participantes
        </Label>
        <div className="relative">
          <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-text focus-within:border-2 focus-within:border-primary">
            <Search className="h-3.5 w-3.5 shrink-0 text-text-muted" />
            <input
              ref={searchInputRef}
              id={fieldId("ufpas_participantes")}
              type="search"
              autoComplete="off"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Busque por nome do titular ou CPF"
              className="h-full flex-1 bg-transparent outline-none placeholder:text-text-muted"
            />
            {buscando && (
              <Spinner className="h-3.5 w-3.5 shrink-0 animate-spin text-text-muted" />
            )}
          </div>

          {query.trim() !== "" && !buscando && (
            <ul
              role="listbox"
              aria-label="Resultados da busca de UFPAs"
              className="absolute left-0 right-0 top-full z-30 mt-1 max-h-64 list-none overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
            >
              {erroBusca ? (
                <li className="px-3 py-3 text-sm text-error-text">{erroBusca}</li>
              ) : resultados.length === 0 ? (
                <li className="px-3 py-3 text-sm text-text-muted">
                  Nenhuma UFPA encontrada.
                </li>
              ) : (
                resultados.map((item) => {
                  const jaAdicionada = ufpas.some((u) => u.id === item.id);
                  return (
                    <li key={item.id} role="option" aria-selected={jaAdicionada}>
                      <button
                        type="button"
                        disabled={jaAdicionada}
                        onClick={() => adicionarUfpa(item)}
                        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span className="truncate text-text">
                          {item.nome_titular}
                        </span>
                        <span className="shrink-0 text-xs tabular-nums text-text-muted">
                          {jaAdicionada ? "Já adicionada" : item.cpf}
                        </span>
                      </button>
                    </li>
                  );
                })
              )}
            </ul>
          )}
        </div>

        {ufpas.length > 0 && (
          <ul className="mt-2 flex list-none flex-wrap gap-2">
            {ufpas.map((u) => (
              <li
                key={u.id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted py-1 pl-3 pr-1 text-xs text-text"
              >
                <span>{u.nome}</span>
                <button
                  type="button"
                  aria-label={`Remover UFPA ${u.nome}`}
                  onClick={() => removerUfpa(u.id)}
                  className="inline-flex h-5 w-5 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text"
                >
                  <X className="h-3 w-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Membros participantes ───────────────────────────────────────── */}
      <fieldset className="flex flex-col gap-2">
        <legend className="text-label font-medium leading-[1.2] text-text">
          Membros participantes
        </legend>

        {ufpas.length === 0 ? (
          <p className="text-xs text-text-muted">
            Selecione ao menos uma UFPA para escolher os membros participantes.
          </p>
        ) : carregandoMembros ? (
          <p className="flex items-center gap-2 text-xs text-text-muted">
            <Spinner className="h-3.5 w-3.5 animate-spin" />
            Carregando atividades…
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {ufpas.map((u) => {
              const lista = membrosPorUfpa[u.id] ?? [];
              const todosMarcados =
                lista.length > 0 && lista.every((m) => selecionados.has(m.id));
              return (
                <div
                  key={u.id}
                  className="rounded-md border border-border bg-surface p-3"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-text">
                      {u.nome}
                    </span>
                    {lista.length > 0 && (
                      <button
                        type="button"
                        onClick={() => toggleTodosDaUfpa(u.id, !todosMarcados)}
                        className="text-xs text-primary hover:underline"
                      >
                        {todosMarcados
                          ? "Desmarcar todos"
                          : "Selecionar todos"}
                      </button>
                    )}
                  </div>

                  {lista.length === 0 ? (
                    <p className="text-xs text-text-muted">
                      Esta UFPA não tem membros cadastrados.
                    </p>
                  ) : (
                    <ul className="grid list-none gap-1 sm:grid-cols-2">
                      {lista.map((m) => (
                        <li key={m.id}>
                          <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm text-text hover:bg-surface-muted">
                            <input
                              type="checkbox"
                              checked={selecionados.has(m.id)}
                              onChange={(e) =>
                                toggleMembro(m, u.id, e.target.checked)
                              }
                              className="h-4 w-4 shrink-0 accent-(--color-primary)"
                            />
                            <span className="truncate">{m.nome_completo}</span>
                            <span className="ml-auto shrink-0 text-xs text-text-muted">
                              {m.grau_parentesco_display}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {errors.membros_participantes && (
          <span
            role="alert"
            className="inline-flex items-center gap-1 text-xs leading-[1.4] text-error-text"
          >
            <ErrorIcon />
            {errors.membros_participantes}
          </span>
        )}
      </fieldset>

      {/* ── Contagem derivada (somente leitura) ─────────────────────────── */}
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface-muted px-3 py-2">
        <span className="text-label font-medium text-text">
          Total de participantes
        </span>
        <output
          id={fieldId("total_participantes")}
          htmlFor={fieldId("ufpas_participantes")}
          aria-live="polite"
          className="ml-auto text-sm font-medium tabular-nums text-text"
        >
          {membros.length}
        </output>
      </div>
      <p className="-mt-3 text-xs text-text-muted">
        Calculado a partir dos membros selecionados. Não é editável.
      </p>
    </div>
  );
}
