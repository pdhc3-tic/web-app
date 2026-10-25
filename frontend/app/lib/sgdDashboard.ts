import { apiClient } from "@/app/lib/api";
import type { StatusDemanda } from "@/app/lib/demandas";
import type { NivelSemaforo } from "@/app/lib/semaforo";

/**
 * Painel consolidado do SGD (#318), consumindo `GET /api/v1/sgd/dashboard/`
 * (BE-11, #315). O recorte por perfil, a ordem da fila e as faixas de saldo
 * são do backend: o front só exibe.
 */

export type ItemFila = {
  id: number;
  titulo: string;
  status: StatusDemanda;
  status_alterado_em: string;
  dias_em_espera: number;
  valor_estimado: string;
  atividade_id: number;
  atividade_titulo: string;
  estado: string;
  territorio: string | null;
};

export type ContagemStatus = { status: StatusDemanda; rotulo: string; total: number };

export type AlertaSaldo = {
  meta_id: number;
  meta_numero: string;
  rubrica_id: number;
  rubrica_slug: string;
  rubrica_nome: string;
  nivel: "nacional" | "estadual" | "territorial";
  estado_sigla: string | null;
  territorio_id: number | null;
  faixa: "amarelo" | "vermelho";
  percentual_comprometido: string;
  valor_aprovado: string;
  valor_comprometido: string;
  saldo_disponivel: string;
};

export type ItemParado = {
  id: number;
  titulo: string;
  status: StatusDemanda;
  status_alterado_em: string;
  dias_uteis_parada: number;
  estado: string;
};

export type SgdDashboard = {
  perfis: string[];
  fila_aguardando_acao: { total: number; itens: ItemFila[] };
  contagem_por_status: ContagemStatus[];
  alertas_saldo: AlertaSaldo[];
  sem_movimentacao: { total: number; itens: ItemParado[] };
};

export async function fetchSgdDashboard(signal?: AbortSignal): Promise<SgdDashboard> {
  const res = await apiClient("/api/v1/sgd/dashboard/", { signal });
  return res.json();
}

/**
 * Faixa do tempo de espera na fila: a partir de 3 dias pede atenção, e de 5 —
 * o mesmo corte da "sem movimentação", em dias úteis no backend — é crítico.
 */
export function faixaDeEspera(dias: number): NivelSemaforo {
  if (dias >= 5) return "vermelho";
  if (dias >= 3) return "amarelo";
  return "verde";
}

export function rotuloDeEspera(dias: number): string {
  if (dias <= 0) return "Hoje";
  return dias === 1 ? "Há 1 dia" : `Há ${dias} dias`;
}

/** Item da fila: o master-detail abre na visão padrão (a fila), já selecionado. */
export function linkDaFila(id: number): string {
  return `/sgd/demandas?demanda=${id}`;
}

/** Demanda parada: pode ser uma devolvida do solicitante, fora da fila — visão Todas. */
export function linkDaParada(id: number): string {
  return `/sgd/demandas?visao=todas&demanda=${id}`;
}

/**
 * Alerta de saldo → Execução por Rubrica filtrada pela célula do alerta. Quem
 * não acessa essa tela (o ADT) vai ao saldo por rubrica do Painel de
 * Orçamento, na mesma meta.
 */
export function linkDoAlerta(alerta: AlertaSaldo, podeVerExecucao: boolean): string {
  if (!podeVerExecucao) return `/sgp/orcamento/?meta=${alerta.meta_id}`;
  const qs = new URLSearchParams({ rubrica: alerta.rubrica_slug, meta: String(alerta.meta_id) });
  if (alerta.territorio_id !== null) qs.set("territorio", String(alerta.territorio_id));
  return `/sgd/execucao?${qs.toString()}`;
}
