"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Gauge, SearchX } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { useCanManageWorkPlan } from "@/app/lib/auth/roles";
import type { Acao } from "@/app/lib/acoes";
import { listMetas, type MetaListItem } from "@/app/lib/metas";
import { acoesNoTerritorio, listTodasAcoes } from "@/app/lib/painel";
import { avaliarAcao } from "@/app/lib/semaforo";
import { fetchTerritoryMap } from "@/app/lib/upfs";
import { AcaoDetalheSlideOver } from "./_components/AcaoDetalheSlideOver";
import { AlertaAcoesCriticas } from "./_components/AlertaAcoesCriticas";
import { MetaResumoCard } from "./_components/MetaResumoCard";
import {
  FILTROS_VAZIOS,
  PainelFilters,
  type PainelFiltersValue,
} from "./_components/PainelFilters";
import type { AcaoAvaliada, MetaComAcoes } from "./_components/tipos";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function PainelAcompanhamentoPage() {
  const { loading: authLoading, canManage } = useCanManageWorkPlan();

  const [metas, setMetas] = useState<MetaListItem[]>([]);
  const [acoes, setAcoes] = useState<Acao[]>([]);
  const [territorios, setTerritorios] = useState<SelectOption[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [filtros, setFiltros] = useState<PainelFiltersValue>(FILTROS_VAZIOS);
  const [selecionada, setSelecionada] = useState<AcaoAvaliada | null>(null);

  /** Ids permitidos pelo filtro de território; `null` = filtro inativo. */
  const [idsNoTerritorio, setIdsNoTerritorio] = useState<Set<number> | null>(
    null,
  );
  const [territorioLoading, setTerritorioLoading] = useState(false);

  // ── Carga do Plano de Trabalho ────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    Promise.all([
      listMetas(controller.signal),
      listTodasAcoes(controller.signal),
    ])
      .then(([m, a]) => {
        setMetas(m);
        setAcoes(a);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o painel. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  // Territórios só alimentam um select — falha aqui não pode derrubar a tela.
  useEffect(() => {
    const controller = new AbortController();

    fetchTerritoryMap(controller.signal)
      .then((mapa) => {
        setTerritorios(
          [...mapa.entries()]
            .map(([id, nome]) => ({ value: String(id), label: nome }))
            .sort((a, b) => a.label.localeCompare(b.label, "pt-BR")),
        );
      })
      .catch(() => {
        // Silencioso: o filtro fica vazio, o resto do painel funciona.
      });

    return () => controller.abort();
  }, []);

  // ── Avaliação do semáforo ─────────────────────────────────────────────────
  const avaliadas: AcaoAvaliada[] = useMemo(() => {
    const porId = new Map(metas.map((m) => [m.id, m]));
    // Uma única referência de "agora" para todas as Ações: instantes diferentes
    // dentro do mesmo render dariam esperados incoerentes entre linhas.
    const hoje = new Date();
    return acoes.map((acao) => {
      const meta = porId.get(acao.meta) ?? null;
      return { acao, meta, avaliacao: avaliarAcao(acao, meta, hoje) };
    });
  }, [acoes, metas]);

  // ── Filtro de território (derivado das Atividades — ver lib/painel.ts) ─────
  useEffect(() => {
    if (filtros.territorio === "" || acoes.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIdsNoTerritorio(null);
      return;
    }

    const controller = new AbortController();
    setTerritorioLoading(true);

    acoesNoTerritorio(acoes, filtros.territorio, controller.signal)
      .then((ids) => {
        if (!controller.signal.aborted) setIdsNoTerritorio(ids);
      })
      .catch(() => {
        // Sem o cruzamento não dá para afirmar o recorte; melhor não filtrar do
        // que exibir uma lista silenciosamente incompleta.
        if (!controller.signal.aborted) setIdsNoTerritorio(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setTerritorioLoading(false);
      });

    return () => controller.abort();
  }, [filtros.territorio, acoes]);

  // ── Aplicação dos filtros ─────────────────────────────────────────────────
  const filtradas = useMemo(() => {
    return avaliadas.filter((item) => {
      if (filtros.meta !== "" && String(item.acao.meta) !== filtros.meta) {
        return false;
      }
      if (idsNoTerritorio && !idsNoTerritorio.has(item.acao.id)) return false;
      return true;
    });
  }, [avaliadas, filtros.meta, idsNoTerritorio]);

  const criticas = useMemo(
    () => filtradas.filter((i) => i.avaliacao.nivel === "vermelho"),
    [filtradas],
  );

  const porMeta: MetaComAcoes[] = useMemo(() => {
    return metas
      .map((meta) => ({
        meta,
        acoes: filtradas.filter((i) => i.acao.meta === meta.id),
      }))
      .filter((g) => g.acoes.length > 0);
  }, [metas, filtradas]);

  const metaOptions: SelectOption[] = useMemo(
    () =>
      metas.map((m) => ({
        value: String(m.id),
        label: `Meta ${m.numero} – ${m.titulo}`,
      })),
    [metas],
  );

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const patchFiltros = useCallback(
    (patch: Partial<PainelFiltersValue>) =>
      setFiltros((prev) => ({ ...prev, ...patch })),
    [],
  );

  const limparFiltros = useCallback(() => setFiltros(FILTROS_VAZIOS), []);

  if (authLoading) return <CenteredSpinner />;

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Painel de Acompanhamento
      </h1>
    </PageHeader>
  );

  if (forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const temFiltro = filtros.meta !== "" || filtros.territorio !== "";
  const baseVazia = !dataLoading && !error && acoes.length === 0;
  const filtroSemResultado =
    !dataLoading && !error && acoes.length > 0 && filtradas.length === 0;

  return (
    <div data-testid="painel-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Acompanhamento" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Semáforo por Ação do Plano de Trabalho. O esperado é a fração do
          período já decorrida; o realizado conta as Atividades de Campo
          concluídas vinculadas a cada Ação.
        </p>

        <PainelFilters
          value={filtros}
          onChange={patchFiltros}
          onClear={limparFiltros}
          metaOptions={metaOptions}
          territorioOptions={territorios}
          optionsLoading={territorios.length === 0}
          territorioLoading={territorioLoading}
        />

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button variant="secondary" onClick={reload}>
              Tentar novamente
            </Button>
          </div>
        ) : dataLoading ? (
          <CenteredSpinner />
        ) : baseVazia ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Gauge className="h-7 w-7" />}
              title="Nenhuma Ação cadastrada ainda."
              description={
                canManage
                  ? "Cadastre Ações nas Metas do Plano de Trabalho para acompanhar a execução aqui."
                  : "As Ações do Plano de Trabalho ainda não foram cadastradas pela UGP."
              }
              action={
                canManage ? (
                  <Button as="a" href="/sgp/metas" variant="primary">
                    Ir para o Plano de Trabalho
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : filtroSemResultado ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<SearchX className="h-7 w-7" />}
              title="Nenhuma Ação corresponde aos filtros"
              description="Ajuste a Meta ou o território para ver as Ações do Plano de Trabalho."
              action={
                temFiltro ? (
                  <Button variant="secondary" onClick={limparFiltros}>
                    Limpar filtros
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <>
            <AlertaAcoesCriticas acoes={criticas} onSelect={setSelecionada} />

            <div className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-text-muted">
                Visão por Meta
              </h2>
              {porMeta.map((g) => (
                <MetaResumoCard
                  key={g.meta.id}
                  item={g}
                  onSelect={setSelecionada}
                  // Filtrou para uma Meta só: esconder as Ações atrás de um
                  // clique a mais não protegeria nada.
                  defaultExpandido={porMeta.length === 1}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <AcaoDetalheSlideOver
        item={selecionada}
        onClose={() => setSelecionada(null)}
        canManage={canManage}
      />
    </div>
  );
}
