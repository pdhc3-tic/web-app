"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Download, ExternalLink } from "lucide-react";
import { AlertCircleIcon } from "@/app/components/icons";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import Spinner from "@/app/components/icons/Spinner";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ExportacaoStatus } from "@/app/components/sgp/Exportacao/ExportacaoStatus";
import { useCanExportWorkPlan, useIsSuperAdmin } from "@/app/lib/auth/roles";
import { criarExportacao, type ResultadoExportacao } from "@/app/lib/exportacoes";
import { FORMATO_OPTIONS, type FormatoExport } from "@/app/lib/exportarPlano";
import { useExportacao } from "@/app/lib/hooks/useExportacao";
import { fetchTerritoryOptions } from "@/app/lib/upfs";
import { listTodasAcoes } from "@/app/lib/painel";
import type { Acao } from "@/app/lib/acoes";

/** Filtros de cada exportação, no contrato do `POST /sgp/exportacoes/`. */
type FiltrosPlano = { formato: FormatoExport; periodo_inicio?: string; periodo_fim?: string };
type FiltrosAtividades = FiltrosPlano & { territorio_id?: string; acao_id?: string };

async function iniciarPlano({ formato, ...filtros }: FiltrosPlano): Promise<ResultadoExportacao> {
  return { tipo: "tarefa", exportacao: await criarExportacao({ tipo: "plano_trabalho", formato, filtros }) };
}

async function iniciarAtividades({ formato, ...filtros }: FiltrosAtividades): Promise<ResultadoExportacao> {
  return { tipo: "tarefa", exportacao: await criarExportacao({ tipo: "atividades", formato, filtros }) };
}

function ExportCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-6">
      <h2 className="text-base font-semibold text-text">{title}</h2>
      <p className="mt-1 text-sm text-text-muted">{description}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-md bg-error-bg px-3 py-2">
      <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-error-text" />
      <p className="text-sm text-error-text">{message}</p>
    </div>
  );
}

export default function RelatoriosPage() {
  // Relatórios é só exportação: quem o backend não deixa exportar (ex.: FGD)
  // não tem o que fazer aqui e vê o acesso restrito.
  const { loading, canExport } = useCanExportWorkPlan();
  const { isSuperAdmin: isAdmin } = useIsSuperAdmin();

  const [territorioOptions, setTerritorioOptions] = useState<SelectOption[]>([]);
  const [acaoOptions, setAcaoOptions] = useState<SelectOption[]>([]);

  useEffect(() => {
    if (!canExport) return;
    const controller = new AbortController();
    Promise.all([
      fetchTerritoryOptions(controller.signal).catch(() => [] as SelectOption[]),
      listTodasAcoes(controller.signal).catch(() => [] as Acao[]),
    ]).then(([territorios, acoes]) => {
      if (controller.signal.aborted) return;
      setTerritorioOptions(territorios);
      setAcaoOptions(
        acoes.map((a) => ({ value: String(a.id), label: `${a.numero} — ${a.descricao}` })),
      );
    });
    return () => controller.abort();
  }, [canExport]);

  // ── Exportação do Plano de Trabalho ────────────────────────────────────────
  // Gerada em segundo plano pelo worker (A4 da #302): a tarefa fica no
  // localStorage, então sair e voltar à página retoma o acompanhamento.
  const plano = useExportacao<FiltrosPlano>({
    chave: "sgp.relatorios.plano-trabalho",
    iniciar: iniciarPlano,
    erroAoIniciar: "Não foi possível exportar o Plano de Trabalho.",
  });
  const [ptFormato, setPtFormato] = useState<FormatoExport>("csv");
  const [ptInicio, setPtInicio] = useState("");
  const [ptFim, setPtFim] = useState("");
  const [ptErro, setPtErro] = useState<string | null>(null);
  const ptBloqueado = plano.iniciando || plano.acompanhando;

  const handleExportarPT = useCallback(() => {
    if (ptInicio && ptFim && ptInicio > ptFim) {
      setPtErro("O início do período não pode ser posterior ao fim.");
      return;
    }
    setPtErro(null);
    void plano.exportar({
      formato: ptFormato,
      periodo_inicio: ptInicio || undefined,
      periodo_fim: ptFim || undefined,
    });
  }, [plano, ptFormato, ptInicio, ptFim]);

  // ── Exportação de Atividades ───────────────────────────────────────────────
  const atividades = useExportacao<FiltrosAtividades>({
    chave: "sgp.relatorios.atividades",
    iniciar: iniciarAtividades,
    erroAoIniciar: "Não foi possível exportar as atividades.",
  });
  const [atFormato, setAtFormato] = useState<FormatoExport>("csv");
  const [atInicio, setAtInicio] = useState("");
  const [atFim, setAtFim] = useState("");
  const [atTerritorio, setAtTerritorio] = useState("");
  const [atAcao, setAtAcao] = useState("");
  const [atErro, setAtErro] = useState<string | null>(null);
  const atBloqueado = atividades.iniciando || atividades.acompanhando;

  const handleExportarAt = useCallback(() => {
    if (atInicio && atFim && atInicio > atFim) {
      setAtErro("O início do período não pode ser posterior ao fim.");
      return;
    }
    setAtErro(null);
    void atividades.exportar({
      formato: atFormato,
      periodo_inicio: atInicio || undefined,
      periodo_fim: atFim || undefined,
      territorio_id: atTerritorio || undefined,
      acao_id: atAcao || undefined,
    });
  }, [atividades, atFormato, atInicio, atFim, atTerritorio, atAcao]);

  const header = (
    <PageHeader>
      <div className="flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-text-muted" />
        <span className="truncate text-base font-semibold text-text">
          Relatórios
        </span>
      </div>
    </PageHeader>
  );

  if (loading) {
    return (
      <>
        {header}
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      </>
    );
  }

  if (!canExport) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  return (
    <>
      {header}

      <div className="mx-auto max-w-4xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Relatórios" },
          ]}
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Relatórios e Exportações
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Exporte dados do SGP conforme o seu escopo territorial.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ExportCard
            title="Plano de Trabalho"
            description="Exporta Metas e Ações com quantidades, valores e semáforo de execução."
          >
            <div className="flex flex-col gap-3">
              <Select
                id="relatorio-pt-formato"
                label="Formato"
                options={FORMATO_OPTIONS}
                value={ptFormato}
                onChange={(v) => setPtFormato(v as FormatoExport)}
                disabled={ptBloqueado}
              />
              <div className="flex flex-wrap gap-3">
                <Input
                  type="date"
                  label="Período — início"
                  className="min-w-36 flex-1"
                  value={ptInicio}
                  onChange={(e) => setPtInicio(e.target.value)}
                  disabled={ptBloqueado}
                />
                <Input
                  type="date"
                  label="Período — fim"
                  className="min-w-36 flex-1"
                  value={ptFim}
                  onChange={(e) => setPtFim(e.target.value)}
                  disabled={ptBloqueado}
                />
              </div>
              {ptErro && <ErrorNote message={ptErro} />}
              {plano.tarefa && (
                <ExportacaoStatus
                  tarefa={plano.tarefa}
                  objeto="do Plano de Trabalho"
                  prefixo="plano"
                  baixando={plano.baixando}
                  erroAcompanhamento={plano.erroAcompanhamento}
                  onBaixar={plano.baixar}
                  onRepetir={plano.repetir}
                  onReconsultar={plano.reconsultar}
                  onDescartar={plano.descartar}
                />
              )}
              <Button
                onClick={handleExportarPT}
                loading={plano.iniciando}
                disabled={plano.acompanhando}
                data-testid="plano-exportar"
                leftIcon={<Download className="h-4 w-4" />}
              >
                Exportar
              </Button>
            </div>
          </ExportCard>

          <ExportCard
            title="Atividades de Campo"
            description="Exporta atividades com equipe, UPFs participantes e status, pelo período selecionado."
          >
            <div className="flex flex-col gap-3">
              <Select
                id="relatorio-at-formato"
                label="Formato"
                options={FORMATO_OPTIONS}
                value={atFormato}
                onChange={(v) => setAtFormato(v as FormatoExport)}
                disabled={atBloqueado}
              />
              <div className="flex flex-wrap gap-3">
                <Input
                  type="date"
                  label="Período — início"
                  className="min-w-36 flex-1"
                  value={atInicio}
                  onChange={(e) => setAtInicio(e.target.value)}
                  disabled={atBloqueado}
                />
                <Input
                  type="date"
                  label="Período — fim"
                  className="min-w-36 flex-1"
                  value={atFim}
                  onChange={(e) => setAtFim(e.target.value)}
                  disabled={atBloqueado}
                />
              </div>
              {territorioOptions.length > 0 && (
                <Select
                  id="relatorio-at-territorio"
                  label="Território"
                  options={territorioOptions}
                  value={atTerritorio}
                  onChange={setAtTerritorio}
                  placeholder="Todos"
                  disabled={atBloqueado}
                />
              )}
              {acaoOptions.length > 0 ? (
                <Select
                  id="relatorio-at-acao"
                  label="Ação"
                  options={acaoOptions}
                  value={atAcao}
                  onChange={setAtAcao}
                  placeholder="Todas"
                  disabled={atBloqueado}
                />
              ) : (
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <Spinner className="h-3 w-3 animate-spin" />
                  Carregando ações…
                </div>
              )}
              {atErro && <ErrorNote message={atErro} />}
              {atividades.tarefa && (
                <ExportacaoStatus
                  tarefa={atividades.tarefa}
                  objeto="das atividades"
                  prefixo="atividades"
                  baixando={atividades.baixando}
                  erroAcompanhamento={atividades.erroAcompanhamento}
                  onBaixar={atividades.baixar}
                  onRepetir={atividades.repetir}
                  onReconsultar={atividades.reconsultar}
                  onDescartar={atividades.descartar}
                />
              )}
              <Button
                onClick={handleExportarAt}
                loading={atividades.iniciando}
                disabled={atividades.acompanhando}
                data-testid="atividades-exportar"
                leftIcon={<Download className="h-4 w-4" />}
              >
                Exportar
              </Button>
            </div>
          </ExportCard>
        </div>

        {isAdmin && (
          <div className="rounded-lg border border-border bg-surface p-6">
            <h2 className="text-base font-semibold text-text">
              Integração Power BI
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              Consulte e regenere o token de serviço utilizado pelo painel Power
              BI.
            </p>
            <div className="mt-4">
              <Link
                href="/admin/integracoes/power-bi"
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-text hover:bg-surface-muted"
              >
                <ExternalLink className="h-4 w-4" />
                Gerenciar integração
              </Link>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
