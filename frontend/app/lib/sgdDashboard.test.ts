import { describe, expect, it } from "vitest";
import {
  faixaDeEspera,
  linkDaFila,
  linkDaParada,
  linkDoAlerta,
  rotuloDeEspera,
  type AlertaSaldo,
} from "@/app/lib/sgdDashboard";

const alerta = (extra: Partial<AlertaSaldo> = {}): AlertaSaldo => ({
  meta_id: 9,
  meta_numero: "2",
  rubrica_id: 4,
  rubrica_slug: "alimentacao-refeicoes",
  rubrica_nome: "Alimentação",
  nivel: "estadual",
  estado_sigla: "RN",
  territorio_id: null,
  faixa: "vermelho",
  percentual_comprometido: "95.00",
  valor_aprovado: "1000.00",
  valor_comprometido: "950.00",
  saldo_disponivel: "50.00",
  ...extra,
});

describe("tempo de espera", () => {
  it("verde até 2 dias, amarelo de 3 a 4, vermelho a partir de 5", () => {
    expect([0, 2, 3, 4, 5, 12].map(faixaDeEspera)).toEqual([
      "verde",
      "verde",
      "amarelo",
      "amarelo",
      "vermelho",
      "vermelho",
    ]);
  });

  it("rótulo em dias", () => {
    expect(rotuloDeEspera(0)).toBe("Hoje");
    expect(rotuloDeEspera(1)).toBe("Há 1 dia");
    expect(rotuloDeEspera(7)).toBe("Há 7 dias");
  });
});

describe("links do painel", () => {
  it("fila na visão padrão; parada na visão Todas, com a demanda selecionada", () => {
    expect(linkDaFila(42)).toBe("/sgd/demandas?demanda=42");
    expect(linkDaParada(42)).toBe("/sgd/demandas?visao=todas&demanda=42");
  });

  it("alerta leva à Execução por Rubrica filtrada pela célula", () => {
    expect(linkDoAlerta(alerta(), true)).toBe("/sgd/execucao?rubrica=alimentacao-refeicoes&meta=9");
    expect(linkDoAlerta(alerta({ nivel: "territorial", estado_sigla: null, territorio_id: 4 }), true)).toBe(
      "/sgd/execucao?rubrica=alimentacao-refeicoes&meta=9&territorio=4",
    );
  });

  it("sem acesso à Execução (ADT), vai ao saldo do Painel de Orçamento", () => {
    expect(linkDoAlerta(alerta({ territorio_id: 4 }), false)).toBe("/sgp/orcamento/?meta=9");
  });
});
