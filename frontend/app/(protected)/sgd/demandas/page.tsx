"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Inbox, Plus, X } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { ApiError } from "@/app/lib/api";
import { canCreateDemanda } from "@/app/lib/auth/roles";
import { getAtividade, listAcoes } from "@/app/lib/atividades";
import {
  DEMANDAS_POR_PAGINA,
  listDemandas,
  type OrdenacaoDemandas,
} from "@/app/lib/demandas";
import {
  CHAVES_FILTRO,
  filtrosDaUrl,
  queryDeFiltros,
  type ExecucaoFiltros,
} from "@/app/lib/execucaoSgd";
import { useFilaDemandas } from "@/app/lib/hooks/useFilaDemandas";
import { qk } from "@/app/lib/queryKeys";
import { listRubricas } from "@/app/lib/tiposSolicitacao";
import { ExportarDemandas } from "../_components/ExportarDemandas";
import { FiltrosDemandas } from "../_components/FiltrosDemandas";
import { DemandaPainel } from "./_components/DemandaPainel";
import { DemandasTabela, DemandasTabelaSkeleton } from "./_components/DemandasTabela";

type Visao = "minha" | "todas";

function Carregando() {
  return (
    <div
      role="status"
      className="flex min-h-[30vh] items-center justify-center gap-2 text-sm text-text-muted"
    >
      <Spinner className="h-5 w-5 animate-spin" />
      Carregando demandas…
    </div>
  );
}

/** Para `navegar`: tira da URL todas as chaves de filtro do `DemandFilter`. */
const SEM_FILTROS = Object.fromEntries(CHAVES_FILTRO.map((k) => [k, null])) as Record<string, null>;

/**
 * Faixa do drill-down do painel de execução (#297): diz de onde vem o recorte,
 * pelo nome da atividade ou da entrega, e volta ao painel com os mesmos filtros.
 * Só aparece quando se chega pelo link do painel (`origem=execucao`, #456): um
 * filtro escolhido aqui não é "recorte do painel".
 */
function RecorteDoPainel({
  recorte,
  onLimpar,
}: {
  recorte: ExecucaoFiltros;
  onLimpar: () => void;
}) {
  const atividade = useQuery({
    queryKey: qk.atividade(recorte.atividade ?? ""),
    queryFn: ({ signal }) => getAtividade(recorte.atividade!, signal),
    enabled: !!recorte.atividade,
    staleTime: Infinity,
  });
  const acoes = useQuery({
    queryKey: qk.acoesPT,
    queryFn: ({ signal }) => listAcoes(signal),
    enabled: !recorte.atividade && !!recorte.acao,
    staleTime: Infinity,
  });

  let alvo: string;
  if (recorte.atividade) {
    alvo = `da atividade “${atividade.data?.titulo ?? `#${recorte.atividade}`}”`;
  } else if (recorte.acao) {
    const acao = acoes.data?.find((a) => String(a.id) === recorte.acao);
    alvo = `da entrega “${acao ? `${acao.numero} — ${acao.descricao}` : `#${recorte.acao}`}”`;
  } else {
    alvo = "do recorte do painel de execução";
  }
  const outros = Object.keys(recorte).filter((k) => k !== "atividade" && k !== "acao").length;

  const voltar = queryDeFiltros(recorte);
  voltar.set("aba", "atividades");

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm text-text"
      data-testid="filtro-atividade-ativo"
    >
      <span>
        Mostrando apenas demandas <strong className="font-semibold">{alvo}</strong>
        {outros > 0 && ` (com mais ${outros} ${outros === 1 ? "filtro" : "filtros"} do painel)`}.
      </span>
      <span className="flex items-center gap-1">
        <Link
          href={`/sgd/execucao?${voltar}`}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          data-testid="filtro-atividade-voltar"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden />
          Voltar ao painel
        </Link>
        <button
          type="button"
          onClick={onLimpar}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          data-testid="filtro-atividade-limpar"
        >
          <X className="h-3 w-3" aria-hidden />
          Limpar filtro
        </button>
      </span>
    </div>
  );
}

function PainelDemandasView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Página da listagem na URL (#323), no `limit`/`offset` do `DemandPagination`:
  // o backend pagina, e a tela pede uma página por vez.
  const pagina = useMemo(() => {
    const limite = Number(searchParams.get("limit"));
    const deslocamento = Number(searchParams.get("offset"));
    return {
      limit: Number.isInteger(limite) && limite > 0 ? limite : DEMANDAS_POR_PAGINA,
      offset: Number.isInteger(deslocamento) && deslocamento > 0 ? deslocamento : 0,
    };
  }, [searchParams]);

  // Ordenação por valor estimado da listagem master-detail (#364), passada ao
  // backend como `?ordering=` (BE-10). Fica na URL para o deep link reproduzir
  // a mesma ordem no retorno pelo histórico.
  const ordenacao: OrdenacaoDemandas | undefined = useMemo(() => {
    const bruto = searchParams.get("ordering");
    return bruto === "valor_estimado_total" || bruto === "-valor_estimado_total"
      ? bruto
      : undefined;
  }, [searchParams]);

  const { data: session } = useSession();
  const fila = useFilaDemandas(pagina, ordenacao);

  // Filtros do `DemandFilter` na URL (#456), escolhidos no painel de filtros ou
  // vindos do drill-down da Execução (#297). O estado manda e a URL só o
  // espelha, como na Execução: dois filtros trocados em seguida não podem
  // partir da URL antiga, que o router ainda não atualizou. Mudança de URL que
  // não veio daqui (voltar, link) reposiciona o estado.
  const query = searchParams.toString();
  const daUrl = useMemo(() => filtrosDaUrl(new URLSearchParams(query)), [query]);
  const [recorte, setRecorte] = useState<ExecucaoFiltros>(daUrl);
  const [queryVista, setQueryVista] = useState(query);
  const [enviadas, setEnviadas] = useState<string[]>([]);
  if (query !== queryVista) {
    setQueryVista(query);
    const minha = enviadas.indexOf(query);
    if (minha >= 0) setEnviadas(enviadas.slice(minha + 1));
    else setRecorte(daUrl);
  }
  const temRecorte = Object.keys(recorte).length > 0;
  const doPainel = temRecorte && searchParams.get("origem") === "execucao";
  // Os filtros valem para "Todas"; a fila de quem decide é curta e não os usa.
  const visao: Visao = temRecorte
    ? "todas"
    : searchParams.get("visao") === "todas" || !fila.decide
      ? "todas"
      : "minha";
  const bruto = searchParams.get("demanda") ?? "";
  const selecionada = /^\d+$/.test(bruto) ? Number(bruto) : null;

  // `keepPreviousData`: ao trocar de página, a anterior fica na tela até a
  // próxima chegar, sem voltar ao skeleton nem "pular" o layout.
  const porRecorte = useQuery({
    queryKey: qk.demandas.recorte(recorte, pagina, ordenacao),
    queryFn: ({ signal }) => listDemandas({ filtros: recorte, pagina, ordenacao }, signal),
    enabled: temRecorte,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  const todas = useQuery({
    queryKey: qk.demandas.lista([], pagina, ordenacao),
    queryFn: ({ signal }) => listDemandas({ pagina, ordenacao }, signal),
    enabled: visao === "todas" && !temRecorte,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  const atual = temRecorte
    ? porRecorte
    : visao === "minha"
      ? fila
      : todas;
  const demandas = atual.data?.demandas ?? [];
  const total = atual.data?.total ?? 0;

  // A página pode ficar além do fim: a última demanda dela foi decidida e saiu
  // da fila, ou o link é antigo. Volta para a última página que existe, em vez
  // de mostrar "nenhuma demanda" sem a paginação para sair dali.
  const alemDoFim =
    atual.isSuccess && !atual.isPlaceholderData && pagina.offset > 0 && pagina.offset >= total;
  useEffect(() => {
    if (!alemDoFim) return;
    const ultima = total > 0 ? Math.floor((total - 1) / pagina.limit) * pagina.limit : 0;
    const next = new URLSearchParams(searchParams.toString());
    if (ultima > 0) next.set("offset", String(ultima));
    else next.delete("offset");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [alemDoFim, total, pagina.limit, searchParams, router, pathname]);

  function navegar(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  /**
   * Troca os filtros: volta à primeira página, fecha a demanda aberta e deixa
   * de ser "recorte do painel". `replace`, como na Execução: cada tecla de uma
   * data não vira uma entrada no histórico.
   */
  const filtrar = useCallback(
    (novos: ExecucaoFiltros) => {
      setRecorte(novos);
      const next = new URLSearchParams(query);
      for (const chave of [...CHAVES_FILTRO, "offset", "demanda", "origem"]) next.delete(chave);
      for (const [chave, valor] of queryDeFiltros(novos)) next.set(chave, valor);
      // Os filtros são da visão "Todas": limpar todos não leva de volta à fila.
      next.set("visao", "todas");
      const nova = next.toString();
      setEnviadas((atuais) => [...atuais, nova]);
      router.replace(nova ? `${pathname}?${nova}` : pathname, { scroll: false });
    },
    [query, pathname, router],
  );

  // Opções de rubrica do filtro, pelo slug (`DemandFilter.rubrica`): as ativas.
  const rubricas = useQuery({
    queryKey: qk.configSgd.rubricas,
    queryFn: ({ signal }) => listRubricas(signal),
    staleTime: 5 * 60_000,
    enabled: visao === "todas",
  });
  const rubricaOptions = useMemo(
    () => (rubricas.data ?? []).filter((r) => r.ativo).map((r) => ({ value: r.slug, label: r.nome })),
    [rubricas.data],
  );

  const erro =
    atual.error instanceof ApiError
      ? atual.error.message
      : atual.error
        ? "Não foi possível carregar as demandas."
        : null;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGD", href: "/sgd" },
          { label: "Demandas" },
        ]}
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Demandas</h1>
          <p className="mt-1 text-sm text-text-muted">
            Pedidos de recurso das atividades, com o fluxo de decisão de cada perfil.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {visao === "todas" && <ExportarDemandas filtros={recorte} />}
          {canCreateDemanda(session?.user) && (
            <Button
              as="a"
              href="/sgd/demandas/nova"
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              data-testid="demandas-nova-btn"
            >
              Nova demanda
            </Button>
          )}
        </div>
      </div>

      {fila.decide && (
        <div
          role="tablist"
          aria-label="Visão das demandas"
          className="inline-flex self-start rounded-md border border-border bg-surface p-0.5"
        >
          {(
            [
              ["minha", `Aguardando minha ação${fila.total !== undefined ? ` (${fila.total})` : ""}`],
              ["todas", "Todas"],
            ] as const
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              role="tab"
              aria-selected={visao === valor}
              onClick={() => {
                // A fila não usa filtros: ir para ela os limpa.
                if (valor === "minha") setRecorte({});
                navegar({
                  ...(valor === "minha" ? { ...SEM_FILTROS, origem: null } : {}),
                  visao: valor === "minha" ? null : "todas",
                  demanda: null,
                  offset: null,
                });
              }}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                visao === valor ? "bg-primary text-surface" : "text-text-muted hover:text-text"
              }`}
              data-testid={`demandas-visao-${valor}`}
            >
              {rotulo}
            </button>
          ))}
        </div>
      )}

      {doPainel && <RecorteDoPainel recorte={recorte} onLimpar={() => filtrar({})} />}

      {visao === "todas" && (
        <FiltrosDemandas
          titulo="Filtros"
          filtros={recorte}
          onChange={filtrar}
          rubricaOptions={rubricaOptions}
          data-testid="demandas-filtros"
        />
      )}

      <div
        className={`grid grid-cols-[minmax(0,1fr)] items-start gap-5 ${
          selecionada !== null ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]" : ""
        }`}
      >
        <div className="min-w-0">
          {atual.isPending ? (
            // Skeleton na mesma grade da tabela (#323): a tabela cresce com o
            // conteúdo, mas as colunas e as alturas são as mesmas — sem "pulo".
            <DemandasTabelaSkeleton compacta={selecionada !== null} />
          ) : erro ? (
            <TabErroSection message={erro} onRetry={() => void atual.refetch()} />
          ) : demandas.length === 0 ? (
            <div className="rounded-lg border border-border bg-surface">
              <EmptyState
                icon={<Inbox className="h-7 w-7" />}
                title={
                  temRecorte
                    ? "Nenhuma demanda com estes filtros"
                    : visao === "minha"
                      ? "Nenhuma demanda aguardando a sua ação"
                      : "Nenhuma demanda por aqui"
                }
                description={
                  temRecorte
                    ? doPainel
                      ? "Nenhuma demanda corresponde ao recorte escolhido no painel de execução."
                      : "Mude ou limpe os filtros para ver outras demandas."
                    : visao === "minha"
                      ? "Quando uma demanda chegar à sua etapa de decisão, ela aparece aqui."
                      : "As demandas visíveis para o seu perfil aparecem aqui."
                }
              />
            </div>
          ) : (
            <div
              className={`flex flex-col gap-2 transition-opacity ${atual.isPlaceholderData ? "opacity-60" : ""}`}
              aria-busy={atual.isPlaceholderData}
              data-testid="demandas-lista"
            >
              <DemandasTabela
                demandas={demandas}
                selecionada={selecionada}
                compacta={selecionada !== null}
                ordenacao={ordenacao}
                onOrdenar={(proxima) =>
                  navegar({ ordering: proxima ?? null, offset: null, demanda: null })
                }
                onSelecionar={(id) => navegar({ demanda: String(id) })}
              />
              {/* Sempre visível (#456): o contador diz quantas há, mesmo numa página só. */}
              <Pagination
                  count={total}
                  offset={pagina.offset}
                  limit={pagina.limit}
                  onOffsetChange={(offset) =>
                    navegar({ offset: offset > 0 ? String(offset) : null, demanda: null })
                  }
                  onLimitChange={(limit) =>
                    navegar({
                      limit: limit === DEMANDAS_POR_PAGINA ? null : String(limit),
                      offset: null,
                      demanda: null,
                    })
                  }
                  itemNoun={{ one: "demanda", other: "demandas" }}
                />
            </div>
          )}
        </div>

        {selecionada !== null && (
          <DemandaPainel
            key={selecionada}
            demandaId={selecionada}
            onFechar={() => navegar({ demanda: null })}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Painel master-detail de Demandas (#296, SGD-RF18 a RF23) — a tela de
 * trabalho do Articulador Estadual, da UGP e da FGD.
 */
export default function PainelDemandasPage() {
  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>
      <Suspense fallback={<Carregando />}>
        <PainelDemandasView />
      </Suspense>
    </>
  );
}
