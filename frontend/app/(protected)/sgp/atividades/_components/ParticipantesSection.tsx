"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { Label } from "@/app/components/ui/Label/Label";
import { ErrorIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { listUpfs, type UpfListItem } from "@/app/lib/upfs";
import { listMembros, type MembroListItem } from "@/app/lib/membros";
import {
  PENDING_UPF_ID,
  fieldId,
  type MembroRef,
  type UpfRef,
} from "./formModel";

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_LIMIT = 10;

type Props = {
  upfs: UpfRef[];
  membros: MembroRef[];
  onChange: (patch: {
    upfs_participantes?: UpfRef[];
    membros_participantes?: MembroRef[];
  }) => void;
  errors: Record<string, string>;
};

/**
 * Seleção de UPFs e membros participantes.
 *
 * A busca de UPF usa o mesmo filtro `q` do módulo Famílias/UPFs (nome do titular
 * ou CPF). Os membros oferecidos são os das UPFs já selecionadas — remover uma
 * UPF remove junto os membros dela. A contagem de participantes é derivada dos
 * membros e nunca editável.
 */
export function ParticipantesSection({
  upfs,
  membros,
  onChange,
  errors,
}: Props) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [resultados, setResultados] = useState<UpfListItem[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);

  const [membrosPorUpf, setMembrosPorUpf] = useState<
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

  // Busca de UPFs por nome do titular ou CPF.
  useEffect(() => {
    const termo = debounced.trim();
    if (termo === "") {
      // Descarta o resultado anterior para não piscar itens obsoletos quando o
      // usuário limpa a busca. Mesmo padrão do CatalogoCombobox do módulo UPF.
      /* eslint-disable react-hooks/set-state-in-effect */
      setResultados([]);
      setBuscando(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      return;
    }
    const controller = new AbortController();
    setBuscando(true);
    setErroBusca(null);
    listUpfs(
      { limit: SEARCH_LIMIT, offset: 0, search: termo, status: "ativas" },
      controller.signal,
    )
      .then((page) => {
        if (controller.signal.aborted) return;
        setResultados(page.results);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setErroBusca("Não foi possível buscar UPFs. Tente novamente.");
        setResultados([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBuscando(false);
      });
    return () => controller.abort();
  }, [debounced]);

  // Carrega os membros de cada UPF selecionada que ainda não está em cache.
  useEffect(() => {
    const pendentes = upfs.filter((u) => !(u.id in membrosPorUpf));
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
        setMembrosPorUpf((prev) => {
          const next = { ...prev };
          for (const [upfId, lista] of pares) next[upfId] = lista;
          return next;
        });

        // Prefill de edição: os membros já selecionados chegam sem nome e sem
        // UPF (só o id). Agora que a lista de cada UPF carregou, dá para
        // completá-los — sem isso, "Desmarcar todos" não os alcançaria.
        const pendentesSelecionados = membrosRef.current.some(
          (m) => m.upfId === PENDING_UPF_ID,
        );
        if (!pendentesSelecionados) return;

        const porId = new Map<number, { nome: string; upfId: number }>();
        for (const [upfId, lista] of pares) {
          for (const m of lista) porId.set(m.id, { nome: m.nome, upfId });
        }
        onChangeRef.current({
          membros_participantes: membrosRef.current.map((m) => {
            if (m.upfId !== PENDING_UPF_ID) return m;
            const resolvido = porId.get(m.id);
            return resolvido ? { id: m.id, ...resolvido } : m;
          }),
        });
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregandoMembros(false);
      });

    return () => controller.abort();
  }, [upfs, membrosPorUpf]);

  const adicionarUpf = useCallback(
    (item: UpfListItem) => {
      if (upfs.some((u) => u.id === item.id)) return;
      onChange({
        upfs_participantes: [
          ...upfs,
          { id: item.id, nome: item.nome_titular, cpf: item.cpf },
        ],
      });
      setQuery("");
      setResultados([]);
      searchInputRef.current?.focus();
    },
    [upfs, onChange],
  );

  const removerUpf = useCallback(
    (upfId: number) => {
      onChange({
        upfs_participantes: upfs.filter((u) => u.id !== upfId),
        // Membros da UPF removida saem junto da seleção.
        membros_participantes: membros.filter((m) => m.upfId !== upfId),
      });
    },
    [upfs, membros, onChange],
  );

  const toggleMembro = useCallback(
    (membro: MembroListItem, upfId: number, marcado: boolean) => {
      onChange({
        membros_participantes: marcado
          ? [
              ...membros,
              { id: membro.id, nome: membro.nome, upfId },
            ]
          : membros.filter((m) => m.id !== membro.id),
      });
    },
    [membros, onChange],
  );

  const toggleTodosDaUpf = useCallback(
    (upfId: number, marcar: boolean) => {
      const lista = membrosPorUpf[upfId] ?? [];
      if (marcar) {
        const jaSelecionados = new Set(membros.map((m) => m.id));
        const novos = lista
          .filter((m) => !jaSelecionados.has(m.id))
          .map((m) => ({ id: m.id, nome: m.nome, upfId }));
        onChange({ membros_participantes: [...membros, ...novos] });
      } else {
        onChange({
          membros_participantes: membros.filter((m) => m.upfId !== upfId),
        });
      }
    },
    [membrosPorUpf, membros, onChange],
  );

  const selecionados = new Set(membros.map((m) => m.id));

  return (
    <div className="flex flex-col gap-4">
      {/* ── Busca de UPFs ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        <Label htmlFor={fieldId("upfs_participantes")}>
          UPFs participantes
        </Label>
        <div className="relative">
          <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-text focus-within:border-2 focus-within:border-primary">
            <Search className="h-3.5 w-3.5 shrink-0 text-text-muted" />
            <input
              ref={searchInputRef}
              id={fieldId("upfs_participantes")}
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
              aria-label="Resultados da busca de UPFs"
              className="absolute left-0 right-0 top-full z-30 mt-1 max-h-64 list-none overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
            >
              {erroBusca ? (
                <li className="px-3 py-3 text-sm text-error-text">{erroBusca}</li>
              ) : resultados.length === 0 ? (
                <li className="px-3 py-3 text-sm text-text-muted">
                  Nenhuma UPF encontrada.
                </li>
              ) : (
                resultados.map((item) => {
                  const jaAdicionada = upfs.some((u) => u.id === item.id);
                  return (
                    <li key={item.id} role="option" aria-selected={jaAdicionada}>
                      <button
                        type="button"
                        disabled={jaAdicionada}
                        onClick={() => adicionarUpf(item)}
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

        {upfs.length > 0 && (
          <ul className="mt-2 flex list-none flex-wrap gap-2">
            {upfs.map((u) => (
              <li
                key={u.id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-muted py-1 pl-3 pr-1 text-xs text-text"
              >
                <span>{u.nome}</span>
                <button
                  type="button"
                  aria-label={`Remover UPF ${u.nome}`}
                  onClick={() => removerUpf(u.id)}
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

        {upfs.length === 0 ? (
          <p className="text-xs text-text-muted">
            Selecione ao menos uma UPF para escolher os membros participantes.
          </p>
        ) : carregandoMembros ? (
          <p className="flex items-center gap-2 text-xs text-text-muted">
            <Spinner className="h-3.5 w-3.5 animate-spin" />
            Carregando atividades…
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {upfs.map((u) => {
              const lista = membrosPorUpf[u.id] ?? [];
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
                        onClick={() => toggleTodosDaUpf(u.id, !todosMarcados)}
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
                      Esta UPF não tem membros cadastrados.
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
                            <span className="truncate">{m.nome}</span>
                            <span className="ml-auto shrink-0 text-xs text-text-muted">
                              {m.parentesco_display}
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
          htmlFor={fieldId("upfs_participantes")}
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
