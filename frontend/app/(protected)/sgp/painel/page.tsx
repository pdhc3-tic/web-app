"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
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
import {
  fetchPainel,
  listTodasAcoes,
  type PainelMetaGrupoApi,
} from "@/app/lib/painel";
import { avaliacaoDaApi } from "@/app/lib/semaforo";
import { fetchTerritoryMap } from "@/app/lib/upfs";
import { AcaoDetalheSlideOver } from "./_components/AcaoDetalheSlideOver";
import { AlertaAcoesCriticas } from "./_components/AlertaAcoesCriticas";
import { MetaResumoCard } from "./_components/MetaResumoCard";
import {
  FILTROS_VAZIOS,
  PainelFilters,
  SITUACOES_VALIDAS,
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

/** Ordena "1.10" depois de "1.9" — comparação numérica, não lexicográfica. */
function compararNumeroAcao(a: string, b: string): number {
  const [aMeta, aAcao] = a.split(".").map(Number);
  const [bMeta, bAcao] = b.split(".").map(Number);
  return (aMeta - bMeta) || (aAcao - bAcao);
}

function PainelAcompanhamentoConteudo() {
  const { loading: authLoading, canManage } = useCanManageWorkPlan();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Dados de apoio, carregados uma única vez.
  const [metas, setMetas] = useState<MetaListItem[]>([]);
  const [detalhes, setDetalhes] = useState<Map<number, Acao>>(new Map());
  const [territorios, setTerritorios] = useState<SelectOption[]>([]);
  const [apoioCarregado, setApoioCarregado] = useState(false);

  // Resultado do painel, refeito a cada mudança de filtro.
  const [grupos, setGrupos] = useState<PainelMetaGrupoApi[] | null>(null);
  const [painelLoading, setPainelLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [selecionada, setSelecionada] = useState<AcaoAvaliada | null>(null);

  // ── Filtros: a URL é o estado ─────────────────────────────────────────────
  // Compartilhar o recorte por link e sobreviver a refresh/voltar sai de graça
  // quando não há cópia local para sincronizar.
  //
  // Os valores são saneados na leitura: a URL é digitável, e o backend responde
  // 400 a um id não numérico. Ignorar o que não pode ser um filtro degrada para
  // "sem filtro" em vez de trocar o painel por uma tela de erro.
  const filtros: PainelFiltersValue = useMemo(() => {
    const id = (chave: string) => {
      const bruto = searchParams.get(chave) ?? "";
      return /^\d+$/.test(bruto) ? bruto : "";
    };
    const situacao = searchParams.get("situacao") ?? "";
    return {
      meta: id("meta"),
      territorio: id("territorio"),
      situacao: SITUACOES_VALIDAS.includes(situacao) ? situacao : "",
    };
  }, [searchParams]);

  const escreverFiltros = useCallback(
    (proximos: PainelFiltersValue) => {
      const qs = new URLSearchParams();
      for (const [chave, valor] of Object.entries(proximos)) {
        if (valor) qs.set(chave, valor);
      }
      const query = qs.toString();
      // `replace` e não `push`: mexer num Select não é navegação, e empilhar
      // uma entrada por tecla obrigaria o usuário a voltar N vezes.
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [router, pathname],
  );

  const patchFiltros = useCallback(
    (patch: Partial<PainelFiltersValue>) =>
      escreverFiltros({ ...filtros, ...patch }),
    [escreverFiltros, filtros],
  );

  const limparFiltros = useCallback(
    () => escreverFiltros(FILTROS_VAZIOS),
    [escreverFiltros],
  );

  // ── Dados de apoio (uma vez) ──────────────────────────────────────────────
  // Metas dão o período dos cards e as opções do filtro; a listagem de Ações dá
  // os campos descritivos que a resposta do painel não carrega.
  useEffect(() => {
    const controller = new AbortController();

    Promise.all([
      listMetas(controller.signal),
      listTodasAcoes(controller.signal),
    ])
      .then(([m, a]) => {
        setMetas(m);
        setDetalhes(new Map(a.map((acao) => [acao.id, acao])));
      })
      .catch(() => {
        // Silencioso: sem o apoio a tela perde rótulos, não o semáforo. O erro
        // que importa é o do painel, tratado no efeito abaixo.
      })
      .finally(() => {
        if (!controller.signal.aborted) setApoioCarregado(true);
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

  // ── Painel (refeito a cada filtro) ────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPainelLoading(true);
    setError(null);

    fetchPainel(
      {
        meta_id: filtros.meta,
        territorio_id: filtros.territorio,
        status_execucao: filtros.situacao,
      },
      controller.signal,
    )
      .then((res) => setGrupos(res.metas))
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
        if (!controller.signal.aborted) setPainelLoading(false);
      });

    return () => controller.abort();
  }, [filtros.meta, filtros.territorio, filtros.situacao, reloadKey]);

  // ── Montagem da tela ──────────────────────────────────────────────────────
  // O agrupamento por Meta já vem pronto do backend; aqui só se acrescenta o
  // que ele não devolve: datas da Meta e campos descritivos da Ação.
  const porMeta: MetaComAcoes[] = useMemo(() => {
    if (!grupos) return [];
    const metaPorId = new Map(metas.map((m) => [m.id, m]));

    return grupos.map((grupo) => {
      const completa = metaPorId.get(grupo.meta.id);
      const meta = {
        ...grupo.meta,
        data_inicio: completa?.data_inicio ?? null,
        data_fim: completa?.data_fim ?? null,
      };

      const acoes = [...grupo.acoes]
        .sort((a, b) => compararNumeroAcao(a.numero, b.numero))
        .map((acao) => ({
          acao,
          detalhe: detalhes.get(acao.id) ?? null,
          meta,
          avaliacao: avaliacaoDaApi(acao, meta),
        }));

      return { meta, acoes };
    });
  }, [grupos, metas, detalhes]);

  const criticas = useMemo(
    () =>
      porMeta.flatMap((g) =>
        g.acoes.filter((i) => i.avaliacao.nivel === "vermelho"),
      ),
    [porMeta],
  );

  const metaOptions: SelectOption[] = useMemo(
    () =>
      metas.map((m) => ({
        value: String(m.id),
        label: `Meta ${m.numero} – ${m.titulo}`,
      })),
    [metas],
  );

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

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

  const temFiltro =
    filtros.meta !== "" || filtros.territorio !== "" || filtros.situacao !== "";
  // Só a primeira carga troca a tela por um spinner. Depois disso o resultado
  // anterior fica visível e esmaecido: piscar a página inteira a cada mexida
  // num Select custa mais orientação do que entrega.
  const primeiraCarga = painelLoading && (grupos === null || !apoioCarregado);
  const semResultado = !painelLoading && !error && porMeta.length === 0;

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
          Semáforo por Ação do Plano de Trabalho, calculado pelo sistema. O
          esperado é a fração do período já decorrida; o realizado conta as
          Atividades de Campo concluídas vinculadas a cada Ação.
        </p>

        <PainelFilters
          value={filtros}
          onChange={patchFiltros}
          onClear={limparFiltros}
          metaOptions={metaOptions}
          territorioOptions={territorios}
          optionsLoading={territorios.length === 0}
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
        ) : primeiraCarga ? (
          <CenteredSpinner />
        ) : semResultado && !temFiltro ? (
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
        ) : semResultado ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<SearchX className="h-7 w-7" />}
              title="Nenhuma Ação corresponde aos filtros"
              description="Ajuste a Meta, o território ou a situação para ver as Ações do Plano de Trabalho."
              action={
                <Button variant="secondary" onClick={limparFiltros}>
                  Limpar filtros
                </Button>
              }
            />
          </div>
        ) : (
          <div
            aria-busy={painelLoading}
            className={`flex flex-col gap-4 transition-opacity ${
              painelLoading ? "opacity-60" : ""
            }`}
          >
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
          </div>
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

/**
 * `useSearchParams` exige um limite de Suspense acima dele — mesmo padrão já
 * usado no detalhe da Meta e nas telas de login.
 */
export default function PainelAcompanhamentoPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <PainelAcompanhamentoConteudo />
    </Suspense>
  );
}
