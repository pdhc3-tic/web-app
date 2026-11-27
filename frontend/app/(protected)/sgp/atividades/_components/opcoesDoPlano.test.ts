import { describe, expect, it } from "vitest";
import type { AcaoPT } from "@/app/lib/atividades";
import { buildAtividadesQuery } from "@/app/lib/atividades";
import { compararNumero, opcoesDoPlano } from "./opcoesDoPlano";

function acao(
  id: number,
  meta: [number, number, string],
  submeta: [number, string, string],
  indicador: [number, string, string],
): AcaoPT {
  return {
    id,
    meta: meta[0],
    meta_numero: meta[1],
    meta_titulo: meta[2],
    submeta: submeta[0],
    submeta_numero: submeta[1],
    submeta_titulo: submeta[2],
    indicador: indicador[0],
    indicador_detalhe: { codigo: indicador[1], nome: indicador[2], unidade_medida: "evento" },
    numero: `${submeta[1]}.${id}`,
    descricao: `Ação ${id}`,
  };
}

const ACOES: AcaoPT[] = [
  acao(1, [12, 6, "Mercados"], [21, "6.1", "Feiras"], [4, "IND-PLA", "Plano"]),
  acao(2, [8, 1, "Organização"], [11, "1.10", "Gestão"], [2, "IND-OFI", "Oficina"]),
  acao(3, [8, 1, "Organização"], [10, "1.2", "Formação"], [2, "IND-OFI", "Oficina"]),
  acao(4, [8, 1, "Organização"], [10, "1.2", "Formação"], [3, "IND-ENC", "Encontro"]),
];

describe("opcoesDoPlano (#464)", () => {
  it("lista cada Meta e cada Indicador uma vez, em ordem", () => {
    const o = opcoesDoPlano(ACOES);
    expect(o.metas).toEqual([
      { value: "8", label: "Meta 1 — Organização" },
      { value: "12", label: "Meta 6 — Mercados" },
    ]);
    expect(o.indicadores.map((i) => i.label)).toEqual([
      "IND-ENC — Encontro",
      "IND-OFI — Oficina",
      "IND-PLA — Plano",
    ]);
  });

  it("as Submetas seguem a Meta escolhida, com 1.10 depois de 1.2", () => {
    const o = opcoesDoPlano(ACOES);
    expect(o.submetasDa("8").map((s) => s.label)).toEqual(["1.2 — Formação", "1.10 — Gestão"]);
    expect(o.submetasDa("12").map((s) => s.value)).toEqual(["21"]);
    expect(o.submetasDa("").map((s) => s.value)).toEqual(["10", "11", "21"]);
  });

  it("sabe a Meta de cada Submeta", () => {
    const o = opcoesDoPlano(ACOES);
    expect(o.metaDaSubmeta("21")).toBe("12");
    expect(o.metaDaSubmeta("999")).toBe("");
  });

  it("compararNumero ordena números hierárquicos", () => {
    expect(["1.10", "1.2", "1", "2.1"].sort(compararNumero)).toEqual(["1", "1.2", "1.10", "2.1"]);
  });
});

describe("buildAtividadesQuery (#464)", () => {
  it("manda meta, submeta e indicador com os nomes do ActivityFilter", () => {
    const qs = new URLSearchParams(
      buildAtividadesQuery({ limit: 20, offset: 0, meta: "8", submeta: "10", indicador: "2" }),
    );
    expect(qs.get("meta")).toBe("8");
    expect(qs.get("submeta")).toBe("10");
    expect(qs.get("indicador")).toBe("2");
  });

  it("sem os filtros, não manda os parâmetros", () => {
    const qs = new URLSearchParams(buildAtividadesQuery({ limit: 20, offset: 0 }));
    expect(qs.has("meta") || qs.has("submeta") || qs.has("indicador")).toBe(false);
  });
});
