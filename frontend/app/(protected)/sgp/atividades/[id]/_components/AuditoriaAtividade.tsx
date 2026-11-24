"use client";

import { History } from "lucide-react";
import { useSession } from "next-auth/react";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import type { AtividadeDetail } from "@/app/lib/atividades";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";

type Props = {
  atividade: Pick<AtividadeDetail, "criado_por" | "criado_em" | "atualizado_em">;
};

/**
 * Procedência do registro: quem criou, quando, e quando mudou pela última vez.
 *
 * `criado_por` vem do detalhe como `{id, nome}` (`UsuarioRef`), ou `null` para
 * registro sem autor (carga inicial, SCA). A ficha tratava o campo como id e
 * mostrava "Usuário #[object Object]" (#449). O id só serve para reconhecer o
 * próprio usuário logado; `null` sai como o traço da `DefinitionList`.
 */
export function AuditoriaAtividade({ atividade }: Props) {
  const { data: session } = useSession();
  const autor = atividade.criado_por;
  const ehVoce = autor !== null && String(autor.id) === String(session?.user?.id);

  return (
    <section className="rounded-lg border border-border bg-surface p-6" data-testid="atividade-auditoria">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-medium text-text">
        <History className="h-4 w-4 text-text-muted" aria-hidden="true" />
        Registro e auditoria
      </h2>
      <DefinitionList
        items={[
          { label: "Criado por", value: autor ? (ehVoce ? `${autor.nome} (você)` : autor.nome) : null },
          { label: "Criado em", value: absoluteDateTime(atividade.criado_em) },
          {
            label: "Última atualização",
            value: (
              <span title={absoluteDateTime(atividade.atualizado_em)}>
                {absoluteDateTime(atividade.atualizado_em)} ({relativeTime(atividade.atualizado_em)})
              </span>
            ),
          },
        ]}
      />
    </section>
  );
}
