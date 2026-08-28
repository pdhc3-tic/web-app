"use client";

import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { rotuloCampo } from "@/app/lib/conflitos";

/** Campos técnicos que não ajudam quem está decidindo. */
const OCULTOS = new Set([
  "id",
  "uuid_local",
  "device_id",
  "criado_em",
  "atualizado_em",
  "ultimo_sync_em",
  "ultima_origem",
  "criado_por",
  "atualizado_por",
  // "dispositivo" na UPF é o meio de acesso à internet, um inteiro de choices —
  // ao lado do dispositivo de coleta exibido acima, só confundiria.
  "dispositivo",
]);

/** Quantos campos exibir antes de cortar — o objeto pode ter dezenas. */
const LIMITE = 10;

/**
 * O registro como está HOJE no servidor, exibido como contexto da decisão.
 *
 * Só entram campos escalares: o serializer devolve o objeto completo, com listas
 * e objetos aninhados que não cabem numa lista de definições — e que não são o
 * que a pessoa precisa para decidir sobre UM campo.
 */
export function RegistroAtual({
  registro,
}: {
  registro: Record<string, unknown> | null;
}) {
  if (!registro) {
    return (
      <section className="rounded-lg border border-border bg-surface p-6">
        <h2 className="text-sm font-medium text-text">Registro no servidor</h2>
        <p className="mt-1 max-w-prose text-sm text-text-muted">
          O registro não foi encontrado pelo identificador da coleta. Ele pode ter
          sido excluído depois que o conflito foi detectado — nesse caso, a
          resolução apenas encerra o conflito, sem alterar dado nenhum.
        </p>
      </section>
    );
  }

  const itens = Object.entries(registro)
    .filter(([chave, valor]) => {
      if (OCULTOS.has(chave)) return false;
      if (valor === null || valor === undefined || valor === "") return false;
      return ["string", "number", "boolean"].includes(typeof valor);
    })
    .slice(0, LIMITE)
    .map(([chave, valor]) => ({
      label: rotuloCampo(chave),
      value: typeof valor === "boolean" ? (valor ? "Sim" : "Não") : String(valor),
    }));

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-medium text-text">Registro no servidor</h2>
        <p className="text-sm text-text-muted">
          Como o registro está agora, para dar contexto à decisão.
        </p>
      </div>

      {itens.length > 0 ? (
        <DefinitionList items={itens} />
      ) : (
        <p className="text-sm text-text-muted">
          Este registro não tem campos simples para exibir.
        </p>
      )}
    </section>
  );
}
