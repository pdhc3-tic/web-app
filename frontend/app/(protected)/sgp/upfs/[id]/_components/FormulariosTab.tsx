"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ClipboardList, Plus } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, formatDate } from "@/app/lib/datetime";
import {
  listFormResponses,
  type FormResponseListItem,
} from "@/app/lib/formularios";
import {
  FormulariosFiltros,
  type FormulariosFiltrosValue,
} from "./FormulariosFiltros";
import { PreencherFormularioSlideOver } from "./PreencherFormularioSlideOver";
import {
  RespostaFormularioSlideOver,
  StatusChip,
} from "./RespostaFormularioSlideOver";

const PAGE_SIZE = 25;

const DEFAULT_FILTERS: FormulariosFiltrosValue = {
  formulario_id: "",
  data_inicio: "",
  data_fim: "",
  respondente: "",
};

/**
 * Chaves de query string que a aba possui na URL. Preservamos qualquer outro
 * parâmetro alheio à aba ao reescrever (ex.: `?tab=` ou `?utm_source=`).
 */
const FILTER_QS_KEYS = [
  "formulario_id",
  "data_inicio",
  "data_fim",
  "respondente",
] as const;

type Props = { upfId: string };

/**
 * Wrapper com Suspense: `useSearchParams` do Next 16 suspende, e este
 * componente é montado dentro do detalhe da UPF (page.tsx), que não fornece
 * o boundary. Sem isto, o build falha com "useSearchParams should be wrapped
 * in a suspense boundary".
 */
export function FormulariosTab({ upfId }: Props) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[30vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      }
    >
      <FormulariosTabView upfId={upfId} />
    </Suspense>
  );
}

function readFiltersFromSearchParams(
  params: URLSearchParams,
): FormulariosFiltrosValue {
  return {
    formulario_id: params.get("formulario_id") ?? "",
    data_inicio: params.get("data_inicio") ?? "",
    data_fim: params.get("data_fim") ?? "",
    respondente: params.get("respondente") ?? "",
  };
}

/**
 * Reflete os filtros na URL preservando o hash da aba (#formularios) e demais
 * query params que não fazem parte deste conjunto. Usa `replaceState` para não
 * poluir o histórico do browser em cada tecla digitada.
 */
function syncFiltersToUrl(filters: FormulariosFiltrosValue) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  for (const key of FILTER_QS_KEYS) {
    const value = filters[key];
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  window.history.replaceState(
    null,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
}

function FormulariosTabView({ upfId }: Props) {
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<FormulariosFiltrosValue>(() =>
    readFiltersFromSearchParams(new URLSearchParams(searchParams.toString())),
  );

  const [page, setPage] = useState(1);
  const [respostas, setRespostas] = useState<FormResponseListItem[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selecionada, setSelecionada] = useState<FormResponseListItem | null>(
    null,
  );
  const [preencherOpen, setPreencherOpen] = useState(false);

  /**
   * Opções do select de formulário: mantido acumulativo com os formulários
   * vistos em qualquer página até agora. Como o BE-16 não expõe um endpoint
   * de "formulários distintos por UPF", derivamos das respostas carregadas
   * — em UPFs típicas isso cobre 100% dos formulários; em cenários com
   * muitas páginas, o usuário paga a expansão à medida que navega.
   */
  const [formularioOptions, setFormularioOptions] = useState<
    Map<string, string>
  >(() => new Map());

  const hasActiveFilters = useMemo(
    () =>
      filters.formulario_id !== "" ||
      filters.data_inicio !== "" ||
      filters.data_fim !== "" ||
      filters.respondente !== "",
    [filters],
  );

  // Zera a página quando qualquer filtro muda (evita "página 5 de 1 resultado").
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1);
  }, [
    filters.formulario_id,
    filters.data_inicio,
    filters.data_fim,
    filters.respondente,
  ]);

  useEffect(() => {
    syncFiltersToUrl(filters);
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listFormResponses(
      upfId,
      {
        page,
        page_size: PAGE_SIZE,
        formulario_id: filters.formulario_id
          ? Number(filters.formulario_id)
          : undefined,
        data_inicio: filters.data_inicio || undefined,
        data_fim: filters.data_fim || undefined,
        respondente: filters.respondente.trim() || undefined,
      },
      controller.signal,
    )
      .then((data) => {
        setRespostas(data.results);
        setCount(data.count);
        setFormularioOptions((prev) => {
          const next = new Map(prev);
          for (const r of data.results) {
            next.set(String(r.formulario_id), r.formulario_nome);
          }
          return next;
        });
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as respostas.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [upfId, page, filters, reloadKey]);

  const formularioSelectOptions = useMemo<SelectOption[]>(
    () =>
      Array.from(formularioOptions.entries())
        .map(([value, label]) => ({ value, label }))
        .sort((a, b) => a.label.localeCompare(b.label, "pt-BR")),
    [formularioOptions],
  );

  const limparFiltros = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const filtros = (
    <FormulariosFiltros
      value={filters}
      onChange={setFilters}
      formularioOptions={formularioSelectOptions}
      disabled={loading && respostas.length === 0 && !hasActiveFilters}
    />
  );

  if (loading && respostas.length === 0) {
    return (
      <div className="space-y-4" data-testid="formularios-tab">
        {filtros}
        <div
          className="flex min-h-[30vh] flex-col items-center justify-center gap-3 text-text-muted"
          role="status"
          aria-live="polite"
          data-testid="formularios-tab-loading"
        >
          <Spinner className="h-6 w-6 animate-spin" />
          <p className="text-sm">Carregando formulários…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4" data-testid="formularios-tab">
        {filtros}
        <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">{error}</p>
          <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
            Tentar novamente
          </Button>
        </div>
      </div>
    );
  }

  if (respostas.length === 0) {
    return (
      <div className="space-y-4" data-testid="formularios-tab">
        {filtros}
        <EmptyState
          icon={<ClipboardList className="h-7 w-7" />}
          title={
            hasActiveFilters
              ? "Nenhuma resposta com esses filtros"
              : "Nenhuma resposta registrada"
          }
          description={
            hasActiveFilters
              ? "Ajuste os filtros ou tente uma busca diferente."
              : "Os formulários preenchidos para esta UPF aparecerão aqui."
          }
          action={
            hasActiveFilters ? (
              <Button variant="secondary" onClick={limparFiltros}>
                Limpar filtros
              </Button>
            ) : (
              <Button
                leftIcon={<Plus className="h-4 w-4" />}
                onClick={() => setPreencherOpen(true)}
                data-testid="formularios-preencher-novo"
              >
                Preencher novo formulário
              </Button>
            )
          }
        />
        <RespostaFormularioSlideOver
          open={selecionada !== null}
          onClose={() => setSelecionada(null)}
          upfId={upfId}
          resposta={selecionada}
        />
        <PreencherFormularioSlideOver
          open={preencherOpen}
          onClose={() => setPreencherOpen(false)}
          upfId={upfId}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="formularios-tab">
      {filtros}

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          {count} {count === 1 ? "resposta registrada" : "respostas registradas"}
        </p>
        <Button
          size="sm"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => setPreencherOpen(true)}
          data-testid="formularios-preencher-novo"
        >
          Preencher novo formulário
        </Button>
      </div>

      <Tabela
        respostas={respostas}
        onSelect={(r) => setSelecionada(r)}
      />

      <Pagination
        count={count}
        offset={(page - 1) * PAGE_SIZE}
        limit={PAGE_SIZE}
        onOffsetChange={(offset) => setPage(Math.floor(offset / PAGE_SIZE) + 1)}
        onLimitChange={() => {}}
        pageSizes={[PAGE_SIZE]}
        itemNoun={{ one: "resposta", other: "respostas" }}
      />

      <RespostaFormularioSlideOver
        open={selecionada !== null}
        onClose={() => setSelecionada(null)}
        upfId={upfId}
        resposta={selecionada}
      />

      <PreencherFormularioSlideOver
        open={preencherOpen}
        onClose={() => setPreencherOpen(false)}
        upfId={upfId}
      />
    </div>
  );
}

function Tabela({
  respostas,
  onSelect,
}: {
  respostas: FormResponseListItem[];
  onSelect: (r: FormResponseListItem) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-180 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Formulário</th>
              <th className="px-4 py-2.5">Versão</th>
              <th className="px-4 py-2.5">Data</th>
              <th className="px-4 py-2.5">Respondente</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {respostas.map((r) => (
              <tr
                key={r.id}
                data-testid={`formulario-row-${r.id}`}
                className="cursor-pointer border-t border-border align-middle transition hover:bg-surface-muted/40"
                onClick={() => onSelect(r)}
              >
                <td className="px-4 py-3 font-medium text-text">
                  {r.formulario_nome}
                </td>
                <td className="px-4 py-3 text-text-muted">
                  {r.formulario_versao}
                </td>
                <td
                  className="px-4 py-3 text-text-muted"
                  title={absoluteDateTime(r.data_preenchimento)}
                >
                  {formatDate(r.data_preenchimento)}
                </td>
                <td className="px-4 py-3 text-text">
                  {r.respondente?.trim() || "Anônimo"}
                </td>
                <td className="px-4 py-3">
                  <StatusChip status={r.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
