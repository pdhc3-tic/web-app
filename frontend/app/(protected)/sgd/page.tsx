"use client";

import { useSession } from "next-auth/react";
import { ArrowLeftRight, FilePlus2, Inbox, PieChart, Scale } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { SubmoduleCard } from "@/app/components/ui/SubmoduleCard/SubmoduleCard";
import {
  canAcessarFilaRemanejamentos,
  canCreateDemanda,
  canOperarArlo,
  canViewSgdGestao,
} from "@/app/lib/auth/roles";
import { useContagemFila } from "@/app/lib/hooks/useFilaDemandas";
import { PainelSgd } from "./_components/PainelSgd";

type Submodule = {
  key: string;
  title: string;
  description: string;
  Icon: LucideIcon;
  href?: string;
  /** Quem enxerga o card. Ausente = todos os autenticados. */
  visivel?: (user: Parameters<typeof canCreateDemanda>[0]) => boolean;
};

/**
 * Home do SGD: o painel consolidado do perfil (#318) e, abaixo, os cards por
 * submódulo, no mesmo padrão das telas-índice do SGP e do SCA.
 */
const SUBMODULES: Submodule[] = [
  {
    key: "painel",
    title: "Painel de Demandas",
    description:
      "Demandas por status, com o fluxo de decisão de cada perfil e o impacto no saldo.",
    Icon: Inbox,
    href: "/sgd/demandas/",
  },
  {
    key: "nova",
    title: "Nova Demanda",
    // As solicitações de recurso (#295) são montadas dentro da demanda, depois de criá-la.
    description:
      "Pedido de recurso para uma atividade: diárias, passagens, veículos, material gráfico, alimentação e equipamentos, com o saldo antes de submeter.",
    Icon: FilePlus2,
    href: "/sgd/demandas/nova/",
    visivel: canCreateDemanda,
  },
  {
    key: "execucao",
    title: "Execução por Rubrica",
    description: "Autorizado, pago e saldo por rubrica, e o custo de cada atividade.",
    Icon: PieChart,
    href: "/sgd/execucao/",
    visivel: canViewSgdGestao,
  },
  {
    key: "remanejamentos",
    title: "Fila de Remanejamentos",
    description:
      "Pedidos de recurso extra das demandas bloqueadas: parecer do Articulador e decisão da UGP.",
    Icon: Scale,
    href: "/sgd/remanejamentos/",
    visivel: canAcessarFilaRemanejamentos,
  },
  {
    key: "arlo",
    title: "Integração Arlo",
    description: "Exportação das demandas autorizadas e importação dos pagamentos.",
    Icon: ArrowLeftRight,
    href: "/sgd/arlo/",
    visivel: canOperarArlo,
  },
];

export default function SGDPage() {
  const { data: session } = useSession();
  const visiveis = SUBMODULES.filter((s) => !s.visivel || s.visivel(session?.user));

  // Pendências de quem decide (Articulador, UGP, FGD) — a mesma fila do badge
  // da sidebar. Para os outros perfis o card não mostra contagem.
  const fila = useContagemFila();
  const pendentes = fila.decide ? (fila.isError ? null : (fila.data?.total ?? null)) : undefined;

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <Breadcrumb items={[{ label: "Início", href: "/dashboard" }, { label: "SGD" }]} />

          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text">
            SGD — Sistema de Gestão de Demandas
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Pedidos de recurso das atividades em campo e o fluxo de aprovação entre
            Articulador Estadual, UGP e FGD.
          </p>
        </div>

        <PainelSgd />

        <h2 className="text-sm font-semibold text-text">Módulos</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visiveis.map((sub) => (
            <SubmoduleCard
              key={sub.key}
              title={sub.title}
              description={sub.description}
              Icon={sub.Icon}
              href={sub.href}
              count={sub.key === "painel" ? pendentes : undefined}
              testId={`sgd-${sub.key}`}
            />
          ))}
        </div>
      </div>
    </>
  );
}
