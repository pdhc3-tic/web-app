"use client";

import { useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Tabs } from "@/app/components/ui/Tabs/Tabs";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { canGerirLimites } from "@/app/lib/auth/roles";
import { formatDate } from "@/app/lib/datetime";
import {
  dataVizinha,
  fetchPerfisOperacionais,
  fetchPeriodicidade,
  hojeIso,
  listLimites,
  periodoDe,
  type LimiteGasto,
} from "@/app/lib/limites";
import { qk } from "@/app/lib/queryKeys";
import { listRubricas } from "@/app/lib/tiposSolicitacao";
import { LimiteSlideOver, type Edicao } from "./_components/LimiteSlideOver";
import { MatrizPadroes } from "./_components/MatrizPadroes";
import { PeriodoNavegador } from "./_components/PeriodoNavegador";
import { SobrescritasTabela } from "./_components/SobrescritasTabela";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

const mensagemDe = (err: unknown) =>
  err instanceof ApiError ? err.message : "Não foi possível carregar os limites.";

/**
 * Gestão dos limites de gasto (#400, §6 do SGP), para Super Admin e UGP.
 *
 * Duas abas sobre o mesmo `SpendingLimit`: o padrão por perfil operacional
 * (matriz rubrica × perfil) e as linhas individuais (sobrescritas e herdadas).
 * O período segue o `budget_limit_period`; só o vigente aceita alterações —
 * os outros ficam para consulta, porque o backend grava sempre no período
 * vigente (ou agenda o seguinte).
 */
export default function LimitesPage() {
  const { data: session, status } = useSession();
  const pode = canGerirLimites(session?.user);
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [aba, setAba] = useState("padroes");
  const hoje = hojeIso();
  const [data, setData] = useState(hoje);
  const [edicao, setEdicao] = useState<Edicao | null>(null);

  const periodicidade = useQuery({
    queryKey: qk.limites.periodicidade,
    queryFn: ({ signal }) => fetchPeriodicidade(signal),
    enabled: pode,
    staleTime: 5 * 60_000,
  });
  const perfis = useQuery({
    queryKey: qk.limites.perfisOperacionais,
    queryFn: ({ signal }) => fetchPerfisOperacionais(signal),
    enabled: pode,
    staleTime: Infinity,
  });
  const rubricas = useQuery({
    queryKey: qk.configSgd.rubricas,
    queryFn: ({ signal }) => listRubricas(signal),
    enabled: pode,
    staleTime: 5 * 60_000,
  });
  const padroes = useQuery({
    queryKey: qk.limites.lista("perfil", data),
    queryFn: ({ signal }) => listLimites({ escopo: "perfil", data }, signal),
    enabled: pode,
  });
  const individuais = useQuery({
    queryKey: qk.limites.lista("individual", data),
    queryFn: ({ signal }) => listLimites({ escopo: "individual", data }, signal),
    enabled: pode,
  });

  const per = periodicidade.data ?? "trimestral";
  const periodo = useMemo(() => periodoDe(data, per), [data, per]);
  const vigente = useMemo(() => periodoDe(hoje, per), [hoje, per]);
  const ehVigente = periodo.inicio === vigente.inicio;
  // Um período adiante basta para ver o padrão agendado para o seguinte.
  const podeAvancar = periodo.inicio <= vigente.inicio;

  const rubricasAtivas = useMemo(() => (rubricas.data ?? []).filter((r) => r.ativo), [rubricas.data]);
  const linhasIndividuais = useMemo(
    () =>
      [...(individuais.data ?? [])].sort(
        (a, b) =>
          (a.user_nome ?? "").localeCompare(b.user_nome ?? "", "pt-BR") ||
          a.rubrica_nome.localeCompare(b.rubrica_nome, "pt-BR"),
      ),
    [individuais.data],
  );

  function onSalvo(limite: LimiteGasto, feita: Edicao) {
    setEdicao(null);
    void queryClient.invalidateQueries({ queryKey: qk.limites.todos });
    // Quem mostra limite em outra tela: a coluna "Limites individuais" da
    // Execução por Rubrica e o saldo da solicitação na montagem da demanda.
    void queryClient.invalidateQueries({ queryKey: ["sgd", "execucao", "painel"] });
    void queryClient.invalidateQueries({ queryKey: ["sgd", "saldo"] });
    // O padrão já em uso não muda no período: o backend agenda o valor novo.
    if (limite.periodo_inicio > vigente.fim) {
      showToast(
        `Padrão alterado. Como já está em uso neste período, o valor novo vale a partir de ${formatDate(limite.periodo_inicio)}.`,
        "success",
      );
      return;
    }
    const nome =
      feita.tipo === "padrao-novo" || feita.tipo === "padrao-alterar"
        ? "Padrão do perfil salvo."
        : "Limite individual salvo.";
    showToast(nome, "success");
  }

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Limites de gasto</h1>
    </PageHeader>
  );

  if (status === "loading") return <CenteredSpinner />;

  if (!pode) {
    return (
      <>
        {header}
        <RestrictedAccess
          title="Limites restritos"
          description="Apenas a UGP e o Super Admin definem os limites de gasto. Você pode acompanhar o seu saldo no Painel de Orçamento."
        />
      </>
    );
  }

  const carregandoBase = periodicidade.isPending || perfis.isPending || rubricas.isPending;
  const erroBase = periodicidade.error ?? perfis.error ?? rubricas.error;

  return (
    <div data-testid="limites-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Orçamento", href: "/sgp/orcamento" },
            { label: "Limites de gasto" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          O padrão do perfil vale para todas as pessoas do perfil. A sobrescrita individual substitui o
          padrão para uma pessoa, com justificativa. Os limites valem por período; o seu saldo
          continua limitado pelo pool do território.
        </p>

        {carregandoBase ? (
          <CenteredSpinner />
        ) : erroBase ? (
          <TabErroSection
            message={mensagemDe(erroBase)}
            onRetry={() => {
              void periodicidade.refetch();
              void perfis.refetch();
              void rubricas.refetch();
            }}
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
              <PeriodoNavegador
                periodo={periodo}
                vigente={ehVigente}
                navegavel={per !== "vigencia"}
                podeAvancar={podeAvancar}
                onAnterior={() => setData(dataVizinha(periodo, -1))}
                onSeguinte={() => setData(dataVizinha(periodo, 1))}
                onVoltarAoVigente={() => setData(hoje)}
              />
              {aba === "sobrescritas" && ehVigente && (
                <Button
                  size="sm"
                  leftIcon={<Plus className="h-4 w-4" />}
                  onClick={() => setEdicao({ tipo: "sobrescrita-nova" })}
                  data-testid="limites-nova-sobrescrita"
                >
                  Nova sobrescrita
                </Button>
              )}
            </div>

            <Tabs
              value={aba}
              onValueChange={setAba}
              aria-label="Limites de gasto"
              items={[
                {
                  id: "padroes",
                  label: "Padrão por perfil",
                  content: padroes.isPending ? (
                    <CenteredSpinner />
                  ) : padroes.error ? (
                    <TabErroSection message={mensagemDe(padroes.error)} onRetry={() => void padroes.refetch()} />
                  ) : (
                    <MatrizPadroes
                      rubricas={rubricasAtivas}
                      perfis={perfis.data ?? []}
                      padroes={padroes.data ?? []}
                      editavel={ehVigente}
                      onDefinir={(perfil, rubrica) => setEdicao({ tipo: "padrao-novo", perfil, rubrica })}
                      onAlterar={(limite, perfil) => setEdicao({ tipo: "padrao-alterar", perfil, limite })}
                    />
                  ),
                },
                {
                  id: "sobrescritas",
                  label: `Sobrescritas individuais${individuais.data ? ` (${individuais.data.length})` : ""}`,
                  content: individuais.isPending ? (
                    <CenteredSpinner />
                  ) : individuais.error ? (
                    <TabErroSection
                      message={mensagemDe(individuais.error)}
                      onRetry={() => void individuais.refetch()}
                    />
                  ) : linhasIndividuais.length === 0 ? (
                    <EmptyState
                      title="Nenhum limite individual neste período"
                      description="Quem não tem linha aqui usa o padrão do perfil. A linha herdada aparece na primeira reserva; a sobrescrita, quando a UGP a cria."
                    />
                  ) : (
                    <SobrescritasTabela
                      linhas={linhasIndividuais}
                      editavel={ehVigente}
                      onAlterar={(limite) => setEdicao({ tipo: "sobrescrita-alterar", limite })}
                    />
                  ),
                },
              ]}
            />
          </>
        )}
      </div>

      <LimiteSlideOver
        edicao={edicao}
        rubricas={rubricasAtivas}
        onClose={() => setEdicao(null)}
        onSalvo={onSalvo}
      />
    </div>
  );
}
