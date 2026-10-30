import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { SolicitacaoDemanda } from "@/app/lib/demandas";
import { bloqueiosDaSubmissao, type ErroSaldoInsuficiente } from "@/app/lib/solicitacoes";
import { SolicitacaoCartao } from "./SolicitacaoCartao";

/**
 * O bloqueio da submissão em cada solicitação, montado pelos campos do
 * `INSUFFICIENT_BALANCE` (#359): a trava, o disponível e o solicitado em BRL
 * e o que fazer — sem ler nada do `detail`.
 */

function solicitacao(id: number, tipoDisplay: string, valor: string): SolicitacaoDemanda {
  return {
    id,
    tipo: "passagem",
    tipo_display: tipoDisplay,
    rubrica_nome: "Passagens Aéreas",
    campos_json: {},
    valor_estimado: valor,
    alerta_rubrica_fora_do_previsto: false,
  } as SolicitacaoDemanda;
}

const DETAIL = "Texto do backend que a tela não usa.";

const individual: ErroSaldoInsuficiente = {
  code: "INSUFFICIENT_BALANCE",
  trava: "individual",
  rubrica: "passagens-aereas",
  disponivel: "5000.00",
  solicitado: "6000.00",
  acao_sugerida: "solicitar_recurso_extra",
  detail: DETAIL,
};

const territorial: ErroSaldoInsuficiente = {
  ...individual,
  trava: "territorial",
  rubrica: "diarias",
  disponivel: "295.00",
  solicitado: "600.00",
  acao_sugerida: "acionar_articulador",
};

function renderCartao(s: SolicitacaoDemanda, bloqueio?: ErroSaldoInsuficiente) {
  const handlers = { onEditar: vi.fn(), onRemover: vi.fn(), onRecursoExtra: vi.fn() };
  render(
    <ul>
      <SolicitacaoCartao solicitacao={s} bloqueio={bloqueio} {...handlers} />
    </ul>,
  );
  return handlers;
}

describe("SolicitacaoCartao — bloqueio da submissão", () => {
  it("limite individual: valores em BRL e o atalho do recurso extra", () => {
    const { onRecursoExtra } = renderCartao(solicitacao(11, "Passagens Aéreas", "6000.00"), individual);

    const bloqueio = screen.getByTestId("bloqueio-11");
    expect(bloqueio).toHaveTextContent("Limite individual insuficiente.");
    expect(screen.getByTestId("bloqueio-valores-11")).toHaveTextContent(
      "Disponível no seu limite: R$ 5.000,00 · Solicitado: R$ 6.000,00",
    );
    expect(bloqueio).toHaveTextContent("Peça recurso extra para cobrir a diferença.");
    expect(bloqueio).not.toHaveTextContent(DETAIL);

    fireEvent.click(screen.getByTestId("recurso-extra-atalho-11"));
    expect(onRecursoExtra).toHaveBeenCalledOnce();
  });

  it("verba do território: valores em BRL, orienta o Articulador e não tem atalho", () => {
    renderCartao(solicitacao(12, "Diárias", "600.00"), territorial);

    const bloqueio = screen.getByTestId("bloqueio-12");
    expect(bloqueio).toHaveTextContent("Verba do território insuficiente.");
    expect(screen.getByTestId("bloqueio-valores-12")).toHaveTextContent(
      "Disponível na verba do território: R$ 295,00 · Solicitado: R$ 600,00",
    );
    expect(bloqueio).toHaveTextContent("Acione o Articulador Estadual para remanejar verba ao território.");
    expect(bloqueio).not.toHaveTextContent(DETAIL);
    expect(screen.queryByTestId("recurso-extra-atalho-12")).not.toBeInTheDocument();
  });

  it("bloqueio múltiplo: cada barrada mostra o seu, e a que coube segue editável sem bloqueio", () => {
    const erro = new ApiError(
      400,
      { code: "INSUFFICIENT_BALANCE", message: "x" },
      { ...individual, solicitacao_id: 11, solicitacoes_bloqueadas: { "11": individual, "12": territorial } },
    );
    const bloqueios = bloqueiosDaSubmissao(erro) ?? {};
    const solicitacoes = [
      solicitacao(11, "Passagens Aéreas", "6000.00"),
      solicitacao(12, "Diárias", "600.00"),
      solicitacao(13, "Locação de veículo", "700.00"),
    ];
    const onEditar = vi.fn();
    render(
      <ul>
        {solicitacoes.map((s) => (
          <SolicitacaoCartao
            key={s.id}
            solicitacao={s}
            bloqueio={bloqueios[s.id]}
            onEditar={() => onEditar(s.id)}
            onRemover={vi.fn()}
            onRecursoExtra={vi.fn()}
          />
        ))}
      </ul>,
    );

    expect(within(screen.getByTestId("solicitacao-11")).getByTestId("bloqueio-11")).toHaveTextContent(
      "Limite individual insuficiente.",
    );
    expect(within(screen.getByTestId("solicitacao-12")).getByTestId("bloqueio-12")).toHaveTextContent(
      "Verba do território insuficiente.",
    );
    expect(screen.queryByTestId("bloqueio-13")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("solicitacao-editar-13"));
    expect(onEditar).toHaveBeenCalledWith(13);
  });
});
