import { describe, expect, it } from "vitest";
import { conflitoDeAtivo, type MapeamentoTipoRubrica } from "@/app/lib/tipoRubrica";

const m = (id: number, tipo: string, ativo: boolean): MapeamentoTipoRubrica => ({
  id,
  tipo,
  rubrica: 1,
  rubrica_nome: "Diárias",
  ativo,
  criado_em: "2026-10-25T10:00:00-03:00",
  atualizado_em: "2026-10-25T10:00:00-03:00",
});

describe("conflitoDeAtivo", () => {
  const lista = [m(1, "diaria", true), m(2, "diaria", false), m(3, "passagem", false)];

  it("um segundo ativo para o mesmo tipo conflita com o ativo existente", () => {
    expect(conflitoDeAtivo(lista, "diaria", null)?.id).toBe(1);
  });

  it("o próprio mapeamento em edição não conflita consigo mesmo", () => {
    expect(conflitoDeAtivo(lista, "diaria", 1)).toBeNull();
  });

  it("reativar um inativo conflita se o tipo já tem outro ativo", () => {
    expect(conflitoDeAtivo(lista, "diaria", 2)?.id).toBe(1);
  });

  it("inativos não contam: o tipo sem ativo fica livre", () => {
    expect(conflitoDeAtivo(lista, "passagem", null)).toBeNull();
  });
});
