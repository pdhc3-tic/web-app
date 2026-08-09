import { apiClient } from "@/app/lib/api";
import type { Acao } from "@/app/lib/acoes";
import type { Paginated } from "@/app/lib/users";

/**
 * Camada de dados do Painel de Acompanhamento (FE-9).
 *
 * A tela carrega o Plano de Trabalho inteiro em duas requisições — as 7 Metas
 * e todas as Ações — e faz o agrupamento em memória. É pouco dado (dezenas de
 * Ações) e evita as 7 chamadas de detalhe que seriam necessárias para extrair
 * `acoes[]` Meta a Meta.
 */

/** GET /api/v1/acoes/ — todas as Ações, sem filtro de Meta. */
export async function listTodasAcoes(signal?: AbortSignal): Promise<Acao[]> {
  const res = await apiClient("/api/v1/acoes/?page_size=100&ordering=numero", {
    signal,
  });
  const data: Paginated<Acao> = await res.json();
  return data.results;
}

// ─── Filtro por território ──────────────────────────────────────────────────

/**
 * Território não é atributo da Ação, e a API de Ações não filtra por ele.
 *
 * O vínculo existe só em Activity → municipio → territory, e o caminho de uma
 * requisição só está fechado: o ActivityListSerializer não devolve `acao`, então
 * não dá para buscar as Atividades do território e agrupá-las por Ação aqui.
 *
 * Sobra perguntar Ação a Ação "existe Atividade sua neste território?", lendo o
 * `count` de uma página de tamanho 1 — a resposta pesa poucos bytes e o
 * ActivityFilter aceita `acao` e `territorio_id` juntos. São dezenas de
 * requisições no pior caso, mitigadas por concorrência limitada e cache, e
 * disparadas apenas quando um território é escolhido.
 *
 * QUANDO O BACKEND ADICIONAR `territorio` ao WorkPlanAcaoFilter, esta função
 * inteira vira `GET /api/v1/acoes/?territorio={id}` — nada mais na tela muda,
 * que é o motivo de o filtro estar isolado aqui. Ver a solicitação aberta com a
 * equipe do backend.
 */

const CONCORRENCIA = 6;

/** Cache de processo: (ação, território) não muda enquanto a aba está aberta. */
const cacheTerritorio = new Map<string, boolean>();

async function temAtividadeNoTerritorio(
  acaoId: number,
  territorioId: string,
  signal?: AbortSignal,
): Promise<boolean> {
  const chave = `${acaoId}:${territorioId}`;
  const emCache = cacheTerritorio.get(chave);
  if (emCache !== undefined) return emCache;

  const qs = new URLSearchParams({
    acao: String(acaoId),
    territorio_id: territorioId,
    page_size: "1",
  });
  const res = await apiClient(`/api/v1/sgp/atividades/?${qs}`, { signal });
  const data: Paginated<unknown> = await res.json();
  const existe = data.count > 0;

  cacheTerritorio.set(chave, existe);
  return existe;
}

/**
 * Ids das Ações com ao menos uma Atividade de Campo no território.
 *
 * O recorte é de EXIBIÇÃO, não de cálculo: o semáforo continua medindo a Ação
 * inteira. Não existe planejamento por território no backend, então dividir um
 * realizado territorial por um planejado global produziria um percentual que
 * não descreve nada — a tela diz isso ao usuário quando o filtro está ativo.
 */
export async function acoesNoTerritorio(
  acoes: ReadonlyArray<Acao>,
  territorioId: string,
  signal?: AbortSignal,
): Promise<Set<number>> {
  const encontradas = new Set<number>();
  const fila = [...acoes];

  async function worker() {
    for (;;) {
      const acao = fila.shift();
      if (!acao) return;
      if (signal?.aborted) return;
      if (await temAtividadeNoTerritorio(acao.id, territorioId, signal)) {
        encontradas.add(acao.id);
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(CONCORRENCIA, acoes.length) }, worker),
  );

  return encontradas;
}
