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
  value: AtividadeElegivel | null;
  onChange: (atividade: AtividadeElegivel | null) => void;
  error?: string;
};

function paraOpcao(a: AtividadeElegivel): SearchSelectOption<AtividadeElegivel> {
  // UF e técnico ajudam a distinguir atividades de mesmo título, agora que a
  // busca não se limita às do solicitante (#361).
  const uf = a.municipio.estado?.sigla;
  const local = uf ? `${a.municipio.nome}/${uf}` : a.municipio.nome;
  const partes = [local, formatDate(a.data_inicio)];
  if (a.tecnico_nome) partes.push(a.tecnico_nome);
  return {
    value: String(a.id),
    label: a.titulo,
    description: partes.join(" · "),
    item: a,
  };
}

/**
 * Campo "Atividade" com busca (#294, caminho alternativo pelo SGD): as
 * atividades em Planejado ou Agendado, buscadas no servidor pelo título.
 *
 * Não filtra por técnico nem por estado (#361): a demanda segue o território
 * de quem a cria, onde quer que a atividade aconteça. O aviso de atividade em
 * outro estado aparece na montagem, com os dados que o backend gravou.
 */
export function AtividadeBusca({ value, onChange, error }: AtividadeBuscaProps) {
  return (
    <SearchSelect<AtividadeElegivel>
      label="Atividade"
      required
      value={value ? paraOpcao(value) : null}
      onChange={(opcao) => onChange(opcao?.item ?? null)}
      search={async (texto, signal) =>
        (await buscarAtividadesElegiveis({ busca: texto }, signal)).map(paraOpcao)
      }
      queryKey={(texto) => qk.atividadesElegiveis(texto)}
      placeholder="Buscar atividades planejadas ou agendadas pelo título…"
      emptyText="Nenhuma atividade planejada ou agendada encontrada."
      renderAside={(o) => (
        <Badge status={badgeStatusFor(o.item.status)} label={o.item.status_display} />
      )}
      error={error}
      data-testid="atividade-busca"
    />
  );
}
