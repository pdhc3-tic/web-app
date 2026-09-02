"use client";

import { ShieldAlert } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import type { BadgeStatus } from "@/app/components/icons";
import { STATUS_LABEL, type ConflitoStatus } from "@/app/lib/conflitos";

/**
 * Status do conflito no vocabulário visual do Badge do design system.
 *
 * `pendente` usa "atrasada" e não "planejado": um conflito parado é uma
 * pendência que alguém precisa resolver, não um item agendado.
 */
const STATUS_BADGE: Record<ConflitoStatus, BadgeStatus> = {
  pendente: "atrasada",
  resolvido_auto: "ativo",
  resolvido_manual: "concluido",
};

export function StatusConflitoBadge({ status }: { status: ConflitoStatus }) {
  return (
    <span data-testid="conflito-status" data-status={status}>
      <Badge status={STATUS_BADGE[status]} label={STATUS_LABEL[status]} />
    </span>
  );
}

/**
 * Marca de campo sensível.
 *
 * Sai do padrão do Badge de propósito: é o único aviso da tela que diz "isto
 * exige decisão humana", e precisa se distinguir dos badges de status que
 * aparecem em toda linha.
 */
export function SensivelBadge({ compacto = false }: { compacto?: boolean }) {
  return (
    <span
      data-testid="conflito-sensivel"
      title="Campo sensível: exige revisão manual e não é resolvido automaticamente."
      className="inline-flex items-center gap-1 rounded-full border border-error-text/35 bg-error-bg px-2 py-0.5 text-2xs font-medium text-error-text whitespace-nowrap"
    >
      <ShieldAlert className="h-3 w-3 shrink-0" aria-hidden />
      {compacto ? "Sensível" : "Campo sensível"}
    </span>
  );
}
