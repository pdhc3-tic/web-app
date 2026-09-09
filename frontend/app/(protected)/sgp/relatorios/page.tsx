"use client";

import { useState } from "react";
import Link from "next/link";
import { BarChart3, Download, ExternalLink } from "lucide-react";
import { useSession } from "next-auth/react";
import { AlertCircleIcon } from "@/app/components/icons";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import Spinner from "@/app/components/icons/Spinner";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { canManageWorkPlan, isSuperAdmin } from "@/app/lib/auth/roles";
import {
  baixarPlanoTrabalho,
  ExportTimeoutError,
  FORMATO_OPTIONS,
  type FormatoExport,
} from "@/app/lib/exportarPlano";
import {
  baixarAtividades,
  type ExportAtividadesFiltros,
} from "@/app/lib/exportarAtividades";

type CardState = "idle" | "exporting" | "error";

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
  const { data: session } = useSession();
  const { showToast } = useToast();

  const canExport = canManageWorkPlan(session?.user);
  const isAdmin = isSuperAdmin(session?.user);

  // ── Exportação do Plano de Trabalho ────────────────────────────────────────
  const [ptFormato, setPtFormato] = useState<FormatoExport>("csv");
  const [ptInicio, setPtInicio] = useState("");
  const [ptFim, setPtFim] = useState("");
  const [ptState, setPtState] = useState<CardState>("idle");
  const [ptErro, setPtErro] = useState<string | null>(null);

  async function handleExportarPT() {
    if (ptInicio && ptFim && ptInicio > ptFim) {
      setPtErro("O início do período não pode ser posterior ao fim.");
      return;
    }
    setPtErro(null);
    setPtState("exporting");
    try {
      const nome = await baixarPlanoTrabalho({
        formato: ptFormato,
        periodo_inicio: ptInicio || undefined,
        periodo_fim: ptFim || undefined,
      });
      showToast(`Download de ${nome} iniciado.`);
      setPtState("idle");
    } catch (e) {
      setPtState("error");
      if (e instanceof ExportTimeoutError) {
        setPtErro("A geração do arquivo passou de 60 s. Tente um período menor.");
      } else if (e instanceof ApiError) {
        setPtErro(e.message);
      } else {
        setPtErro("Não foi possível exportar o Plano de Trabalho.");
      }
    }
  }

  // ── Exportação de Atividades ───────────────────────────────────────────────
  const [atFormato, setAtFormato] = useState<FormatoExport>("csv");
  const [atInicio, setAtInicio] = useState("");
  const [atFim, setAtFim] = useState("");
  const [atState, setAtState] = useState<CardState>("idle");
  const [atErro, setAtErro] = useState<string | null>(null);

  async function handleExportarAt() {
    if (atInicio && atFim && atInicio > atFim) {
      setAtErro("O início do período não pode ser posterior ao fim.");
      return;
    }
    setAtErro(null);
    setAtState("exporting");
    try {
      const filtros: ExportAtividadesFiltros = {
        formato: atFormato,
        periodo_inicio: atInicio || undefined,
        periodo_fim: atFim || undefined,
      };
      const nome = await baixarAtividades(filtros);
      showToast(`Download de ${nome} iniciado.`);
      setAtState("idle");
    } catch (e) {
      setAtState("error");
      if (e instanceof ExportTimeoutError) {
        setAtErro("A geração do arquivo passou de 60 s. Tente um período menor.");
      } else if (e instanceof ApiError) {
        setAtErro(e.message);
      } else {
        setAtErro("Não foi possível exportar as atividades.");
      }
    }
  }

  return (
    <>
      <PageHeader>
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-text-muted" />
          <span className="truncate text-base font-semibold text-text">
            Relatórios
          </span>
        </div>
      </PageHeader>

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
                label="Formato"
                options={FORMATO_OPTIONS}
                value={ptFormato}
                onChange={(v) => setPtFormato(v as FormatoExport)}
                disabled={ptState === "exporting"}
              />
              <div className="flex flex-wrap gap-3">
                <Input
                  type="date"
                  label="Período — início"
                  className="min-w-36 flex-1"
                  value={ptInicio}
                  onChange={(e) => setPtInicio(e.target.value)}
                  disabled={ptState === "exporting"}
                />
                <Input
                  type="date"
                  label="Período — fim"
                  className="min-w-36 flex-1"
                  value={ptFim}
                  onChange={(e) => setPtFim(e.target.value)}
                  disabled={ptState === "exporting"}
                />
              </div>
              {ptErro && <ErrorNote message={ptErro} />}
              <Button
                onClick={handleExportarPT}
                loading={ptState === "exporting"}
                disabled={!canExport}
                leftIcon={<Download className="h-4 w-4" />}
              >
                Exportar
              </Button>
              {!canExport && (
                <p className="text-xs text-text-muted">
                  Disponível para UGP e Super Admin.
                </p>
              )}
            </div>
          </ExportCard>

          <ExportCard
            title="Atividades de Campo"
            description="Exporta atividades com equipe, UPFs participantes e status, pelo período selecionado."
          >
            <div className="flex flex-col gap-3">
              <Select
                label="Formato"
                options={FORMATO_OPTIONS}
                value={atFormato}
                onChange={(v) => setAtFormato(v as FormatoExport)}
                disabled={atState === "exporting"}
              />
              <div className="flex flex-wrap gap-3">
                <Input
                  type="date"
                  label="Período — início"
                  className="min-w-36 flex-1"
                  value={atInicio}
                  onChange={(e) => setAtInicio(e.target.value)}
                  disabled={atState === "exporting"}
                />
                <Input
                  type="date"
                  label="Período — fim"
                  className="min-w-36 flex-1"
                  value={atFim}
                  onChange={(e) => setAtFim(e.target.value)}
                  disabled={atState === "exporting"}
                />
              </div>
              {atErro && <ErrorNote message={atErro} />}
              <Button
                onClick={handleExportarAt}
                loading={atState === "exporting"}
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
