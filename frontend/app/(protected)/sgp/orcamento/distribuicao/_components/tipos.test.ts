import { describe, expect, it } from "vitest";
import type { PoolOrcamentoApi } from "@/app/lib/orcamento";
import { projetar, SEM_PAI, tetoDoPool, type Destino, type Teto } from "./tipos";

/** #398 — o teto da distribuição sai do pool de cima, com as parcelas prontas do painel. */

function pool(p: Partial<PoolOrcamentoApi>): PoolOrcamentoApi {
  return {
    id: 1,
    rubrica: { id: 1, slug: "diarias", nome: "Diárias" },
    nivel: "nacional",
    estado: null,
    territorio: null,
    reserva_ugp: false,
    valor_aprovado: "0.00",
    valor_distribuido: "0.00",
    valor_comprometido: "0.00",
    valor_executado: "0.00",
    saldo_disponivel: "0.00",
    saldo_pool: "0.00",
    semaforo: "verde",
    alerta_80: false,
    limiares_semaforo: { amarelo: 70, vermelho: 90 },
    ...p,
  };
}

describe("tetoDoPool (#398)", () => {
  it("sem pool de cima, ou com ele zerado, não há teto", () => {
    expect(tetoDoPool(null)).toBe(SEM_PAI);
    expect(tetoDoPool(pool({ valor_aprovado: "0.00" }))).toBe(SEM_PAI);
  });

  it("o saldo do pai desconta o comprometido e o executado; o disponível, o já distribuído", () => {
    const teto = tetoDoPool(
      pool({ valor_aprovado: "100000.00", valor_comprometido: "5000.00", valor_executado: "2000.00", valor_distribuido: "60000.00" }),
    ) as Teto;
    expect(teto).toEqual({
      alocadoNoPai: 100000,
      consumidoNoPai: 7000,
      saldoDoPai: 93000,
      jaDistribuido: 60000,
      disponivel: 33000,
    });
  });
});

describe("projetar sobre os pools de baixo (#398)", () => {
  const teto = tetoDoPool(pool({ valor_aprovado: "100000.00", valor_distribuido: "60000.00" })) as Teto;
  const destinos: Destino[] = [
    { id: 20, nome: "Rio Grande do Norte (RN)", pool: pool({ id: 2, nivel: "estadual", valor_aprovado: "60000.00" }) },
    { id: 15, nome: "Paraíba (PB)", pool: null },
  ];

  it("ajustar o pool existente conta só a diferença; criar o novo conta o valor inteiro", () => {
    const p = projetar(teto, destinos, { 20: 70000, 15: 35000 });
    expect(p.total).toBe(105000);
    expect(p.excedenteConjunto).toBe(5000);
    expect(p.excedentePorDestino).toEqual({ 20: 0, 15: 0 });
    expect(p.emEdicao).toEqual([20, 15]);
  });

  it("um destino sozinho acima do saldo do pai é barrado", () => {
    expect(projetar(teto, destinos, { 15: 45000 }).excedentePorDestino[15]).toBe(5000);
  });
});
