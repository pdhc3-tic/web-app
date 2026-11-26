import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AcaoNested, AcaoPT } from "@/app/lib/atividades";
import type { ContextoDemanda } from "@/app/lib/demandas";
import {
  CadeiaPlanoTrabalho,
  cadeiaDaAcaoPT,
  cadeiaDaAtividade,
  cadeiaDaDemanda,
  type CadeiaPT,
} from "./CadeiaPlanoTrabalho";

const ESPERADA: CadeiaPT = {
  acao: { numero: "1.1.1", descricao: "Realizar oficinas de organização produtiva" },
  submeta: { numero: "1.1", titulo: "Formação para a organização produtiva" },
  meta: { numero: 1, titulo: "Fortalecimento da organização produtiva das famílias" },
  indicador: { codigo: "IND-OFI", nome: "Oficina", unidade_medida: "evento" },
};

describe("CadeiaPlanoTrabalho (#446)", () => {
  it("os três formatos da API viram a mesma cadeia", () => {
    const daLista: AcaoPT = {
      id: 1,
      meta: 10,
      numero: "1.1.1",
      descricao: "Realizar oficinas de organização produtiva",
      meta_numero: 1,
      meta_titulo: "Fortalecimento da organização produtiva das famílias",
      submeta_numero: "1.1",
      submeta_titulo: "Formação para a organização produtiva",
      indicador_detalhe: { codigo: "IND-OFI", nome: "Oficina", unidade_medida: "evento" },
    };
    const daAtividade: AcaoNested = {
      id: 1,
      numero: "1.1.1",
      descricao: "Realizar oficinas de organização produtiva",
      meta: { id: 10, numero: 1, titulo: "Fortalecimento da organização produtiva das famílias" },
      submeta: { id: 20, numero: "1.1", titulo: "Formação para a organização produtiva" },
      indicador: { id: 2, codigo: "IND-OFI", nome: "Oficina", unidade_medida: "evento" },
    };
    const contexto = {
      acao_numero: "1.1.1",
      acao_descricao: "Realizar oficinas de organização produtiva",
      submeta_numero: "1.1",
      submeta_titulo: "Formação para a organização produtiva",
      meta_numero: 1,
      meta_titulo: "Fortalecimento da organização produtiva das famílias",
      indicador_codigo: "IND-OFI",
      indicador_nome: "Oficina",
      indicador_unidade_medida: "evento",
    } as ContextoDemanda;

    expect(cadeiaDaAcaoPT(daLista)).toEqual(ESPERADA);
    expect(cadeiaDaAtividade(daAtividade)).toEqual(ESPERADA);
    expect(cadeiaDaDemanda(contexto)).toEqual(ESPERADA);
  });

  it("mostra Ação, Submeta, Meta e Indicador, nessa ordem e com a unidade", () => {
    render(<CadeiaPlanoTrabalho cadeia={ESPERADA} prefixo="cadeia" />);

    const rotulos = screen.getAllByRole("term").map((t) => t.textContent);
    expect(rotulos).toEqual(["Ação", "Submeta", "Meta", "Indicador"]);
    expect(screen.getByTestId("cadeia-acao")).toHaveTextContent("1.1.1 — Realizar oficinas de organização produtiva");
    expect(screen.getByTestId("cadeia-submeta")).toHaveTextContent("1.1 — Formação para a organização produtiva");
    expect(screen.getByTestId("cadeia-meta")).toHaveTextContent(
      "Meta 1 — Fortalecimento da organização produtiva das famílias",
    );
    expect(screen.getByTestId("cadeia-indicador")).toHaveTextContent("IND-OFI — Oficina (unidade: evento)");
  });
});
