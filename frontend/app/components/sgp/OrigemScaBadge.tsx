"use client";

import { Badge } from "@/app/components/ui/Badge/Badge";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";

/** Recorte comum a UPF, Membro e Atividade — os campos de sync do backend. */
export type ComOrigemSca = {
  ultima_origem: "sca" | "web";
  ultimo_sync_em: string | null;
};

/**
 * Marca que a versão mais recente do registro veio do aplicativo de campo.
 *
 * A regra é `ultima_origem === "sca"`, e não `device_id` preenchido: o
 * `device_id` fica gravado para sempre depois do primeiro sync, então usá-lo
 * faria a badge continuar afirmando "veio do app" mesmo depois de alguém editar
 * a ficha pela web. Os viewsets do SGP gravam `ultima_origem="web"` em todo
 * create e update, então o campo acompanha de fato a última edição.
 *
 * O sync grava `ultimo_sync_em` sempre junto de `ultima_origem="sca"`
 * (apps/sca/sync_entities.py), então a data do tooltip nunca falta — mas a
 * badge continua aparecendo se algum dia faltar, porque a procedência é a
 * informação principal e a data é o detalhe.
 */
export function OrigemScaBadge({ registro }: { registro: ComOrigemSca }) {
  if (registro.ultima_origem !== "sca") return null;

  const sincronizadoEm = registro.ultimo_sync_em;
  const titulo = sincronizadoEm
    ? `Sincronizado em ${absoluteDateTime(sincronizadoEm)} (${relativeTime(sincronizadoEm)})`
    : "Registro originado no aplicativo de campo.";

  return (
    <span data-testid="badge-origem-sca" title={titulo}>
      <Badge status="info" label="Registrado via SCA" />
    </span>
  );
}
