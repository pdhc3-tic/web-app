"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Layers, PieChart } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { canViewSgdGestao } from "@/app/lib/auth/roles";
import {
  fetchCustoPorAtividade,
  fetchPainelRubricas,
  filtrosDaUrl,
  queryDeFiltros,
  type ExecucaoFiltros,
} from "@/app/lib/execucaoSgd";
import { qk } from "@/app/lib/queryKeys";
import { CustoPorAtividadeTable } from "./_components/CustoPorAtividadeTable";
import { ExecucaoFilters } from "./_components/ExecucaoFilters";
import { ExportarButton } from "./_components/ExportarButton";
import { PainelRubricasTable } from "./_components/PainelRubricasTable";

type Aba = "rubricas" | "atividades";

function mensagemDeErro(erro: unknown): string {
  if (erro instanceof ApiError && erro.status === 403) {
    return "Acesso restrito aos perfis de gestão do SGD (Super Admin, UGP, FGD e Articulador).";
  }
  if (erro instanceof ApiError && erro.message) return erro.message;
  return "Não foi possível carregar os dados de execução.";
}

/**
 * Execução por rubrica e custo por atividade (#297 · SGD-FE-4). Aba e filtros
 * ficam na URL: o drill-down para a lista de demandas e o "voltar" preservam o
 * recorte.
 */
function ExecucaoView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const query = searchParams.toString();
  const daUrl = useMemo(() => {
    const params = new URLSearchParams(query);
    return {
      aba: (params.get("aba") === "atividades" ? "atividades" : "rubricas") as Aba,
      filtros: filtrosDaUrl(params),
    };
  }, [query]);

  // O estado manda e a URL só o espelha: dois filtros trocados em seguida não
  // podem partir da URL antiga, que o router ainda não atualizou. Mudança de
  // URL que não veio daqui (voltar, link) reposiciona o estado.
  const [estado, setEstado] = useState(daUrl);
  const [queryVista, setQueryVista] = useState(query);
  const [enviadas, setEnviadas] = useState<string[]>([]);
  if (query !== queryVista) {
    setQueryVista(query);
    const minha = enviadas.indexOf(query);
    if (minha >= 0) setEnviadas(enviadas.slice(minha + 1));
    else setEstado(daUrl);
  }
  const { aba, filtros } = estado;

  const navegar = useCallback(
    (novaAba: Aba, novosFiltros: ExecucaoFiltros) => {
      setEstado({ aba: novaAba, filtros: novosFiltros });
      const qs = queryDeFiltros(novosFiltros);
      if (novaAba === "atividades") qs.set("aba", "atividades");
      const nova = qs.toString();
      setEnviadas((atuais) => [...atuais, nova]);
      router.replace(nova ? `${pathname}?${nova}` : pathname, { scroll: false });
    },
    [pathname, router],
  );

  const painel = useQuery({
    queryKey: qk.execucao.painel(filtros),
    queryFn: ({ signal }) => fetchPainelRubricas(filtros, signal),
    enabled: aba === "rubricas",
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const custo = useQuery({
    queryKey: qk.execucao.custo(filtros),
    queryFn: ({ signal }) => fetchCustoPorAtividade(filtros, signal),
    enabled: aba === "atividades",
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  // As opções de rubrica saem do painel sem filtros: o backend lista todas as
  // rubricas ativas, mesmo sem movimentação.
  const rubricas = useQuery({
    queryKey: qk.execucao.painel({}),
    queryFn: ({ signal }) => fetchPainelRubricas({}, signal),
    staleTime: 5 * 60_000,
  });
  const rubricaOptions = (rubricas.data ?? []).map((r) => ({
    value: r.rubrica_slug,
    label: r.rubrica_nome,
  }));

  const atual = aba === "rubricas" ? painel : custo;

  const abaClasse = (ativa: boolean) =>
    `flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
      ativa
        ? "border-primary font-semibold text-primary"
        : "border-transparent text-text-muted hover:text-text"
    }`;

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Execução por Rubrica e Custos
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Acompanhamento orçamentário das demandas do SGD e relatório de custos das atividades.
          </p>
        </div>
        <ExportarButton filtros={filtros} />
      </div>

      <div role="tablist" aria-label="Visão da execução" className="flex border-b border-border">
        <button
          type="button"
          role="tab"
          aria-selected={aba === "rubricas"}
          onClick={() => navegar("rubricas", filtros)}
          className={abaClasse(aba === "rubricas")}
          data-testid="tab-rubricas"
        >
          <PieChart className="h-4 w-4" aria-hidden />
          <span>Painel por Rubrica</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={aba === "atividades"}
          onClick={() => navegar("atividades", filtros)}
          className={abaClasse(aba === "atividades")}
          data-testid="tab-custo-atividades"
        >
          <Layers className="h-4 w-4" aria-hidden />
          <span>Custo por Atividade</span>
        </button>
      </div>

      <ExecucaoFilters
        filtros={filtros}
        onChange={(novos) => navegar(aba, novos)}
        rubricaOptions={rubricaOptions}
      />

      <div aria-busy={atual.isFetching}>
        {atual.isPending ? (
          <div className="flex justify-center py-16" data-testid="carregando-spinner">
            <Spinner className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : atual.isError ? (
          <TabErroSection message={mensagemDeErro(atual.error)} onRetry={() => void atual.refetch()} />
        ) : aba === "rubricas" ? (
          <PainelRubricasTable linhas={painel.data ?? []} />
        ) : (
          <CustoPorAtividadeTable entregas={custo.data ?? []} filtros={filtros} />
        )}
        {atual.isFetching && !atual.isPending && (
          <p role="status" className="mt-2 flex items-center gap-2 text-xs text-text-muted">
            <Spinner className="h-3 w-3 animate-spin" /> Atualizando…
          </p>
        )}
      </div>
    </>
  );
}

export default function ExecucaoSgdPage() {
  const { data: session, status } = useSession();

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">Execução por Rubrica</span>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6" data-testid="execucao-page">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGD", href: "/sgd" },
            { label: "Execução por Rubrica" },
          ]}
        />

        {status === "loading" ? (
          <div className="flex items-center gap-2 py-10 text-sm text-text-muted">
            <Spinner className="h-4 w-4" /> Carregando…
          </div>
        ) : !canViewSgdGestao(session?.user) ? (
          <RestrictedAccess description="O painel de execução é dos perfis de gestão do SGD: Super Admin, UGP, FGD e Articulador Estadual." />
        ) : (
          <Suspense
            fallback={
              <div className="flex justify-center py-16">
                <Spinner className="h-8 w-8 animate-spin text-primary" />
              </div>
            }
          >
            <ExecucaoView />
          </Suspense>
        )}
      </div>
    </>
  );
}
