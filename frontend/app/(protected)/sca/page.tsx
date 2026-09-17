"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  ClipboardList,
  FileSignature,
  GitCompareArrows,
  History,
  ShieldOff,
  Smartphone,
  WifiOff,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { SubmoduleCard } from "@/app/components/ui/SubmoduleCard/SubmoduleCard";
import {
  canReviewSyncConflicts,
  canViewScaAdmin,
  isSuperAdmin,
} from "@/app/lib/auth/roles";
import { fetchDeviceCount } from "@/app/lib/sca";

type Submodule = {
  key: string;
  title: string;
  description: string;
  Icon: LucideIcon;
  href?: string;
  /**
   * Quem enxerga o card. Ausente = todos os autenticados. Espelha a permissão
   * do backend da tela correspondente — esconder um card cujo destino
   * responderia 403 evita mandar o usuário para a tela de acesso negado.
   */
  visivel?: (user: Parameters<typeof canViewScaAdmin>[0]) => boolean;
};

/**
 * Tela-índice do SCA, no mesmo padrão da do SGP: cards por submódulo, os
 * ativos navegáveis e os planejados como "Em breve", para dar a visão do
 * escopo do módulo.
 *
 * Existe porque as telas administrativas do SCA (#156, #157, #158) foram
 * entregues sem ponto de entrada: `/sca` era um placeholder sem links, e o
 * painel de dispositivos não tinha nenhuma referência no app inteiro — só se
 * chegava nele digitando a URL.
 *
 * Os itens "Em breve" saem do escopo descrito no placeholder que esta tela
 * substituiu; nenhum deles tem rota hoje.
 */
const SUBMODULES: Submodule[] = [
  {
    key: "dispositivos",
    title: "Dispositivos",
    description:
      "Aparelhos registrados, último sync e registros pendentes de envio.",
    Icon: Smartphone,
    href: "/sca/dispositivos/",
    visivel: canViewScaAdmin,
  },
  {
    key: "sync-events",
    title: "Log de Sincronização",
    description:
      "Histórico de push e pull por técnico e dispositivo, com os erros de cada envio.",
    Icon: History,
    href: "/sca/sync-events/",
    visivel: canViewScaAdmin,
  },
  {
    key: "conflitos",
    title: "Conflitos de Sincronização",
    description:
      "Divergências entre o dado local e o do servidor, para revisão e resolução.",
    Icon: GitCompareArrows,
    href: "/sca/conflitos/",
    visivel: canReviewSyncConflicts,
  },
  {
    key: "acessos",
    title: "Acessos ao App",
    description:
      "Revogação e reativação do acesso dos técnicos ao aplicativo de campo.",
    Icon: ShieldOff,
    href: "/admin/acessos-sca/",
    visivel: isSuperAdmin,
  },
  {
    key: "coleta",
    title: "Coleta Offline",
    description:
      "Captura em campo sem conectividade, com envio em lote no retorno.",
    Icon: WifiOff,
  },
  {
    key: "formularios",
    title: "Formulários em Campo",
    description: "Formulários publicados pelo SGF disponíveis no aplicativo.",
    Icon: ClipboardList,
  },
  {
    key: "evidencias",
    title: "Fotos e Assinaturas",
    description: "Evidências de visita: imagens, GPS e assinatura do titular.",
    Icon: FileSignature,
  },
];

export default function SCAPage() {
  const { data: session } = useSession();
  const user = session?.user;

  const visiveis = SUBMODULES.filter((s) => !s.visivel || s.visivel(user));
  const podeVerDispositivos = canViewScaAdmin(user);

  // `null` = carregando ou erro silencioso → o card mostra "—" sem travar a
  // tela. Só busca para quem enxerga o card, senão a chamada seria um 403 certo.
  const [deviceCount, setDeviceCount] = useState<number | null>(null);

  useEffect(() => {
    if (!podeVerDispositivos) return;
    const controller = new AbortController();

    fetchDeviceCount(controller.signal)
      .then(setDeviceCount)
      .catch(() => {
        // Silencioso: o card fica com "—" e o resto da tela segue.
      });

    return () => controller.abort();
  }, [podeVerDispositivos]);

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SCA</span>
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <Breadcrumb
            items={[{ label: "Início", href: "/dashboard" }, { label: "SCA" }]}
          />

          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text">
            SCA — Sistema de Coleta em Campo
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Acompanhamento dos dispositivos em campo e da sincronização dos
            dados coletados. Os submódulos do aplicativo entram nas próximas
            sprints.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visiveis.map((sub) => (
            <SubmoduleCard
              key={sub.key}
              title={sub.title}
              description={sub.description}
              Icon={sub.Icon}
              href={sub.href}
              count={sub.key === "dispositivos" ? deviceCount : undefined}
            />
          ))}
        </div>
      </div>
    </>
  );
}
