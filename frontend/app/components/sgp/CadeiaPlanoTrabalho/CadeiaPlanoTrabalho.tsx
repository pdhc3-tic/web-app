import { DefinitionList, type DefinitionItem } from "@/app/components/ui/DefinitionList/DefinitionList";
import type { AcaoNested, AcaoPT } from "@/app/lib/atividades";
import type { ContextoDemanda } from "@/app/lib/demandas";

/**
 * Cadeia do Plano de Trabalho de uma Ação (SGP-RF07; SGD-RF02, #446): Ação,
 * Submeta, Meta e Indicador, sempre nessa ordem e só leitura. Cada tela recebe
 * a cadeia num formato da API; os adaptadores abaixo a normalizam.
 */
export type CadeiaPT = {
  acao: { numero: string; descricao: string };
  submeta: { numero: string; titulo: string };
  meta: { numero: number; titulo: string };
  indicador: { codigo: string; nome: string; unidade_medida: string };
};

/** Da Ação do `GET /api/v1/acoes/` (formulário da atividade). */
export function cadeiaDaAcaoPT(acao: AcaoPT): CadeiaPT {
  return {
    acao: { numero: acao.numero, descricao: acao.descricao },
    submeta: { numero: acao.submeta_numero, titulo: acao.submeta_titulo },
    meta: { numero: acao.meta_numero, titulo: acao.meta_titulo },
    indicador: indicadorDe(acao.indicador_detalhe),
  };
}

/** Da Ação aninhada no detalhe da atividade. */
export function cadeiaDaAtividade(acao: AcaoNested): CadeiaPT {
  return {
    acao: { numero: acao.numero, descricao: acao.descricao },
    submeta: { numero: acao.submeta.numero, titulo: acao.submeta.titulo },
    meta: { numero: acao.meta.numero, titulo: acao.meta.titulo },
    indicador: indicadorDe(acao.indicador),
  };
}

function indicadorDe(i: CadeiaPT["indicador"]): CadeiaPT["indicador"] {
  return { codigo: i.codigo, nome: i.nome, unidade_medida: i.unidade_medida };
}

/** Do contexto da demanda, que vem achatado. */
export function cadeiaDaDemanda(contexto: ContextoDemanda): CadeiaPT {
  return {
    acao: { numero: contexto.acao_numero, descricao: contexto.acao_descricao },
    submeta: { numero: contexto.submeta_numero, titulo: contexto.submeta_titulo },
    meta: { numero: contexto.meta_numero, titulo: contexto.meta_titulo },
    indicador: {
      codigo: contexto.indicador_codigo,
      nome: contexto.indicador_nome,
      unidade_medida: contexto.indicador_unidade_medida,
    },
  };
}

/**
 * Os quatro níveis como itens de `DefinitionList`, para entrar numa lista que
 * já existe (ficha da atividade, painel da demanda). Cada valor leva o
 * `data-testid` `{prefixo}-{nivel}`.
 *
 * A unidade sai como o backend manda (`evento`, `plano`): os rótulos dela
 * chegam em `/choices/` com o PR #475 (#473).
 */
export function itensDaCadeia(cadeia: CadeiaPT, prefixo: string): DefinitionItem[] {
  const { acao, submeta, meta, indicador } = cadeia;
  return [
    {
      label: "Ação",
      value: <span data-testid={`${prefixo}-acao`}>{`${acao.numero} — ${acao.descricao}`}</span>,
    },
    {
      label: "Submeta",
      value: <span data-testid={`${prefixo}-submeta`}>{`${submeta.numero} — ${submeta.titulo}`}</span>,
    },
    {
      label: "Meta",
      value: <span data-testid={`${prefixo}-meta`}>{`Meta ${meta.numero} — ${meta.titulo}`}</span>,
    },
    {
      label: "Indicador",
      value: (
        <span data-testid={`${prefixo}-indicador`}>
          {`${indicador.codigo} — ${indicador.nome}`}
          <span className="font-normal text-text-muted">{` (unidade: ${indicador.unidade_medida})`}</span>
        </span>
      ),
    },
  ];
}

/** A cadeia sozinha, num bloco próprio (formulário da atividade). */
export function CadeiaPlanoTrabalho({ cadeia, prefixo }: { cadeia: CadeiaPT; prefixo: string }) {
  return (
    <section
      className="rounded-md border border-border bg-surface-muted/40 px-4 py-3"
      aria-label="Cadeia do Plano de Trabalho"
      data-testid={prefixo}
    >
      <p className="mb-2 text-xs text-text-muted">Vínculo com o Plano de Trabalho, definido pela Ação escolhida.</p>
      <DefinitionList items={itensDaCadeia(cadeia, prefixo)} />
    </section>
  );
}
