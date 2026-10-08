"use client";

import { Badge } from "@/app/components/ui/Badge/Badge";
import {
  SearchSelect,
  type SearchSelectOption,
} from "@/app/components/ui/SearchSelect/SearchSelect";
import { badgeStatusFor } from "@/app/lib/atividades";
import { formatDate } from "@/app/lib/datetime";
import {
  buscarAtividadesElegiveis,
  type AtividadeElegivel,
} from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";

type AtividadeBuscaProps = {
  /** Usuário logado — a busca cobre só as atividades dele (RF01). */
  tecnicoId: string;
  value: AtividadeElegivel | null;
  onChange: (atividade: AtividadeElegivel | null) => void;
  error?: string;
};

function paraOpcao(a: AtividadeElegivel): SearchSelectOption<AtividadeElegivel> {
  return {
    value: String(a.id),
    label: a.titulo,
    description: `${a.municipio.nome} · ${formatDate(a.data_inicio)}`,
    item: a,
  };
}

/**
 * Campo "Atividade" com busca (#294, caminho alternativo pelo SGD): as
 * atividades do solicitante em Planejado ou Agendado, buscadas no servidor.
 *
 * Enquanto o `ActivityFilter` não aceitar `q` e vários `status`, o texto
 * digitado não estreita o resultado e só vêm as Agendadas
 * (docs/pendencias-backend-sprint-10.md, item 9).
 */
export function AtividadeBusca({ tecnicoId, value, onChange, error }: AtividadeBuscaProps) {
  return (
    <SearchSelect<AtividadeElegivel>
      label="Atividade"
      required
      value={value ? paraOpcao(value) : null}
      onChange={(opcao) => onChange(opcao?.item ?? null)}
      search={async (texto, signal) =>
        (await buscarAtividadesElegiveis({ tecnicoId, busca: texto }, signal)).map(paraOpcao)
      }
      queryKey={(texto) => qk.atividadesElegiveis(tecnicoId, texto)}
      placeholder="Buscar entre as suas atividades planejadas ou agendadas…"
      emptyText="Nenhuma atividade planejada ou agendada encontrada."
      renderAside={(o) => (
        <Badge status={badgeStatusFor(o.item.status)} label={o.item.status_display} />
      )}
      disabled={!tecnicoId}
      error={error}
      data-testid="atividade-busca"
    />
  );
}
