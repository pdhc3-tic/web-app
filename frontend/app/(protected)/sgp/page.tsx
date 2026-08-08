"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Calendar,
  ClipboardCheck,
  ClipboardList,
  Sprout,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { fetchUpfCount } from "@/app/lib/upfs";
import { SubmoduleCard } from "./_components/SubmoduleCard";

type Submodule = {
  key: string;
  title: string;
  description: string;
  Icon: LucideIcon;
  href?: string;
};

// Submódulos do SGP conforme Doc SGP §1.1. Apenas Famílias/UPFs está ativo nesta sprint;
// os demais entram como "Em breve" (sem href) para dar a visão do escopo total do módulo.
const SUBMODULES: Submodule[] = [
  {
    key: "upfs",
    title: "Famílias / UPFs",
    description: "Cadastro de famílias e unidades produtivas familiares.",
    Icon: Users,
    href: "/sgp/upfs/",
  },
  {
    key: "atividades",
    title: "Atividades de Campo",
    description: "Registro e acompanhamento das atividades em campo.",
    Icon: ClipboardList,
    href: "/sgp/atividades/",
  },
  {
    key: "calendario",
    title: "Calendário",
    description: "Agenda de visitas, eventos e prazos do território.",
    Icon: Calendar,
    href: "/sgp/atividades/calendario/",
  },
  {
    key: "plano",
    title: "Plano de Trabalho",
    description: "Metas do PDHC III, com período, ODS e valor planejado.",
    Icon: ClipboardCheck,
    href: "/sgp/metas/",
  },
  {
    key: "producao",
    title: "Produção da UPF",
    description: "Dados de produção e cadeias produtivas da unidade.",
    Icon: Sprout,
  },
  {
    key: "relatorios",
    title: "Relatórios",
    description: "Indicadores e relatórios consolidados do módulo.",
    Icon: BarChart3,
  },
];

export default function SGPPage() {
  // `null` = carregando ou erro silencioso → o card exibe "—" sem bloquear o layout.
  const [upfCount, setUpfCount] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchUpfCount(controller.signal)
      .then((count) => setUpfCount(count))
      .catch(() => {
        // Erro silencioso: mantém "—" e não interrompe a renderização da tela.
      });

    return () => controller.abort();
  }, []);

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGP</span>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <Breadcrumb
            items={[{ label: "Início", href: "/dashboard" }, { label: "SGP" }]}
          />

          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text">
            SGP — Sistema de Gestão de Projetos
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Selecione um submódulo para começar. Novos submódulos serão
            liberados nas próximas sprints.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {SUBMODULES.map((sub) => (
            <SubmoduleCard
              key={sub.key}
              title={sub.title}
              description={sub.description}
              Icon={sub.Icon}
              href={sub.href}
              count={sub.key === "upfs" ? upfCount : undefined}
            />
          ))}
        </div>
      </div>
    </>
  );
}
