import type { SelectOption } from "@/app/components/ui/Select/Select";
import type { AcaoPT } from "@/app/lib/atividades";

/**
 * Opções dos filtros de Meta, Submeta e Indicador da lista de Atividades
 * (#464), tiradas das Ações que a tela já carrega (`GET /api/v1/acoes/`, com a
 * cadeia nomeada desde o #445). Cada perfil só vê Metas, Submetas e
 * Indicadores que têm Ação no seu escopo, e não há chamada a mais.
 */
export type OpcoesDoPlano = {
  metas: SelectOption[];
  indicadores: SelectOption[];
  /** Submetas da Meta escolhida; sem Meta, todas. */
  submetasDa: (metaId: string) => SelectOption[];
  /** Meta a que a Submeta pertence ("" se a Submeta não está na lista). */
  metaDaSubmeta: (submetaId: string) => string;
};

/** Compara números hierárquicos ("1.10" depois de "1.9"). */
export function compararNumero(a: string, b: string): number {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? -1) - (pb[i] ?? -1);
    if (d !== 0) return d;
  }
  return 0;
}

export function opcoesDoPlano(acoes: AcaoPT[]): OpcoesDoPlano {
  const metas = new Map<number, { numero: number; titulo: string }>();
  const submetas = new Map<number, { meta: number; numero: string; titulo: string }>();
  const indicadores = new Map<number, { codigo: string; nome: string }>();

  for (const a of acoes) {
    metas.set(a.meta, { numero: a.meta_numero, titulo: a.meta_titulo });
    submetas.set(a.submeta, { meta: a.meta, numero: a.submeta_numero, titulo: a.submeta_titulo });
    indicadores.set(a.indicador, { codigo: a.indicador_detalhe.codigo, nome: a.indicador_detalhe.nome });
  }

  const opcoesMeta = [...metas.entries()]
    .sort(([, x], [, y]) => x.numero - y.numero)
    .map(([id, m]) => ({ value: String(id), label: `Meta ${m.numero} — ${m.titulo}` }));

  const opcoesIndicador = [...indicadores.entries()]
    .sort(([, x], [, y]) => x.codigo.localeCompare(y.codigo, "pt-BR"))
    .map(([id, i]) => ({ value: String(id), label: `${i.codigo} — ${i.nome}` }));

  const todasSubmetas = [...submetas.entries()].sort(([, x], [, y]) => compararNumero(x.numero, y.numero));

  return {
    metas: opcoesMeta,
    indicadores: opcoesIndicador,
    submetasDa: (metaId) =>
      todasSubmetas
        .filter(([, s]) => !metaId || String(s.meta) === metaId)
        .map(([id, s]) => ({ value: String(id), label: `${s.numero} — ${s.titulo}` })),
    metaDaSubmeta: (submetaId) => {
      const s = submetas.get(Number(submetaId));
      return s ? String(s.meta) : "";
    },
  };
}
