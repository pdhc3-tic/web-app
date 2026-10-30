import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  PainelRubricasTable,
  PainelRubricasTableSkeleton,
} from "./PainelRubricasTable";

/**
 * Testes do painel por rubrica (#323): o skeleton precisa renderizar a mesma
 * grade da tabela (seis colunas, cabeçalho igual) para a troca não gerar o
 * salto de layout que o critério 1 da issue pede para corrigir.
 */

describe("PainelRubricasTableSkeleton", () => {
  it("renderiza o cabeçalho real e N linhas de esqueleto", () => {
    render(<PainelRubricasTableSkeleton linhas={5} />);

    const node = screen.getByTestId("painel-rubricas-skeleton");
    expect(node).toBeInTheDocument();

    // Mesmo cabeçalho da tabela real — a largura das colunas é a mesma.
    expect(screen.getByText("Rubrica")).toBeInTheDocument();
    expect(screen.getByText("Solicitado")).toBeInTheDocument();
    expect(screen.getByText("Autorizado")).toBeInTheDocument();
    expect(screen.getByText("Executado")).toBeInTheDocument();
    expect(screen.getByText("Disponível")).toBeInTheDocument();
    expect(screen.getByText(/Semáforo/)).toBeInTheDocument();

    // Cinco linhas de esqueleto no `tbody`.
    const linhas = node.querySelectorAll("tbody tr");
    expect(linhas).toHaveLength(5);

    // Nada do conteúdo da tabela real: nenhum dado numérico "cru".
    expect(screen.queryByTestId("tabela-painel-rubricas")).not.toBeInTheDocument();
  });

  it("escondido do leitor de tela com aria-hidden", () => {
    render(<PainelRubricasTableSkeleton />);
    // O skeleton é decorativo — o estado "carregando" é indicado pelo
    // `aria-busy` do contêiner, que mora na página.
    expect(screen.getByTestId("painel-rubricas-skeleton")).toHaveAttribute(
      "aria-hidden",
    );
  });

  it("usa 6 linhas por default quando nenhum número é passado", () => {
    render(<PainelRubricasTableSkeleton />);
    const node = screen.getByTestId("painel-rubricas-skeleton");
    expect(node.querySelectorAll("tbody tr")).toHaveLength(6);
  });
});

describe("PainelRubricasTable — contrato com a página", () => {
  it("mostra a mensagem de vazio quando não há rubricas", () => {
    render(<PainelRubricasTable linhas={[]} />);
    expect(screen.getByText(/Nenhuma rubrica encontrada/)).toBeInTheDocument();
    expect(
      screen.queryByTestId("tabela-painel-rubricas"),
    ).not.toBeInTheDocument();
  });

  it("renderiza a tabela com os dados quando há linhas", () => {
    render(
      <PainelRubricasTable
        linhas={[
          {
            rubrica_id: 1,
            rubrica_slug: "alimentacao-refeicoes",
            rubrica_nome: "Alimentação/Refeições",
            solicitado: "10000",
            autorizado: "9000",
            executado: "5000",
            disponivel: "4000",
            percentual_execucao: "55.55",
            faixa: "amarelo",
          },
        ]}
      />,
    );

    expect(screen.getByTestId("tabela-painel-rubricas")).toBeInTheDocument();
    expect(
      screen.getByTestId("rubrica-linha-alimentacao-refeicoes"),
    ).toBeInTheDocument();
  });
});
