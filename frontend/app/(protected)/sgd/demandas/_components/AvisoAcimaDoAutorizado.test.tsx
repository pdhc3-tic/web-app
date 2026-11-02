import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AvisoAcimaDoAutorizado } from "./AvisoAcimaDoAutorizado";

describe("AvisoAcimaDoAutorizado (#360)", () => {
  it("mostra a diferença em BRL quando o pago passa do autorizado", () => {
    render(<AvisoAcimaDoAutorizado solicitacaoId={1} pago="1200.50" autorizado="1000.00" />);
    expect(screen.getByTestId("aviso-acima-do-autorizado-1").textContent).toContain(
      "200,50 acima do autorizado; será registrado no relatório de risco de glosa.",
    );
  });

  it.each(["1000.00", "800", ""])("não avisa com o valor pago %j", (pago) => {
    render(<AvisoAcimaDoAutorizado solicitacaoId={1} pago={pago} autorizado="1000.00" />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
