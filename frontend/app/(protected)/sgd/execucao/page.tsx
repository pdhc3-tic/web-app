"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Layers, PieChart } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { ApiError } from "@/app/lib/api";
import {
  fetchCustoPorAtividade,
  fetchPainelRubricas,
  type EntregaCusto,
  type ExecucaoFiltros,
  type LinhaPainelRubrica,
} from "@/app/lib/execucaoSgd";
import { CustoPorAtividadeTable } from "./_components/CustoPorAtividadeTable";
import { ExecucaoFilters } from "./_components/ExecucaoFilters";
import { ExportarButton } from "./_components/ExportarButton";
import { PainelRubricasTable } from "./_components/PainelRubricasTable";

type AbaAtiva = "rubricas" | "atividades";

export default function ExecucaoSgdPage() {
  const [aba, setAba] = useState<AbaAtiva>("rubricas");
  const [filtros, setFiltros] = useState<ExecucaoFiltros>({});

  const [linhasRubricas, setLinhasRubricas] = useState<LinhaPainelRubrica[]>([]);
  const [entregasCusto, setEntregasCusto] = useState<EntregaCusto[]>([]);

  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setCarregando(true);
    setErro(null);

    const carregarDados = async () => {
      try {
        if (aba === "rubricas") {
          const dados = await fetchPainelRubricas(
            {
              territorio: filtros.territorio,
              meta: filtros.meta,
              estado: filtros.estado,
            },
            controller.signal,
          );
          if (!controller.signal.aborted) {
            setLinhasRubricas(dados);
          }
        } else {
          const dados = await fetchCustoPorAtividade(filtros, controller.signal);
          if (!controller.signal.aborted) {
            setEntregasCusto(dados);
          }
        }
      } catch (e: unknown) {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setErro("Acesso restrito aos perfis de gestão do SGD (Super Admin, UGP, FGD e Articulador).");
        } else if (e instanceof ApiError) {
          setErro(e.message || "Não foi possível carregar os dados de execução.");
        } else {
          setErro("Erro de conexão ao carregar o painel.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setCarregando(false);
        }
      }
    };

    carregarDados();

    return () => controller.abort();
  }, [aba, filtros, reloadKey]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "SGD", href: "/sgd" },
          { label: "Execução por Rubrica" },
        ]}
      />

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

      {/* Navegação entre Abas */}
      <div className="flex border-b border-border">
        <button
          type="button"
          onClick={() => setAba("rubricas")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
            aba === "rubricas"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-text-muted hover:text-text"
          }`}
          data-testid="tab-rubricas"
        >
          <PieChart className="h-4 w-4" />
          <span>Painel por Rubrica</span>
        </button>

        <button
          type="button"
          onClick={() => setAba("atividades")}
          className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
            aba === "atividades"
              ? "border-primary text-primary font-semibold"
              : "border-transparent text-text-muted hover:text-text"
          }`}
          data-testid="tab-custo-atividades"
        >
          <Layers className="h-4 w-4" />
          <span>Custo por Atividade</span>
        </button>
      </div>

      {/* Filtros da visão */}
      <ExecucaoFilters filtros={filtros} onChange={setFiltros} />

      {/* Área de conteúdo */}
      {carregando ? (
        <div className="flex justify-center py-16" data-testid="carregando-spinner">
          <Spinner className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : erro ? (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-12 text-center shadow-xs">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-md text-sm text-text-muted" data-testid="erro-mensagem">
            {erro}
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setReloadKey((k) => k + 1)}
            data-testid="tentar-novamente-btn"
          >
            Tentar novamente
          </Button>
        </div>
      ) : aba === "rubricas" ? (
        <PainelRubricasTable linhas={linhasRubricas} />
      ) : (
        <CustoPorAtividadeTable entregas={entregasCusto} />
      )}
    </div>
  );
}
