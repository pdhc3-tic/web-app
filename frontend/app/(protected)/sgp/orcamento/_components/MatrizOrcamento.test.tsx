import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PoolOrcamentoApi } from "@/app/lib/orcamento";
import { montarMatriz } from "./matriz";
import { MatrizOrcamento } from "./MatrizOrcamento";

/** #398 — a matriz Rubrica × Nível como o UGP, o Articulador e o ADT a veem. */

const DIARIAS = { id: 1, slug: "diarias", nome: "Diárias" };
let id = 100;
function pool(p: Partial<PoolOrcamentoApi> & Pick<PoolOrcamentoApi, "nivel">): PoolOrcamentoApi {
  return {
    id: id++,
    rubrica: DIARIAS,
    estado: null,
    territorio: null,
    reserva_ugp: false,
    valor_aprovado: "10000.00",
    valor_distribuido: "0.00",
    valor_comprometido: "2000.00",
    valor_executado: "1000.00",
    valor_executado_meta: "300.00",
    saldo_disponivel: "7000.00",
    saldo_pool: "7000.00",
    semaforo: "verde",
    alerta_80: false,
    limiares_semaforo: { amarelo: 70, vermelho: 90 },
    ...p,
  };
}
const RN = { id: 20, sigla: "RN", nome: "Rio Grande do Norte" };
const nacional = pool({ nivel: "nacional", valor_aprovado: "100000.00", valor_distribuido: "10000.00" });
const estadual = pool({ nivel: "estadual", estado: RN });
const territorial = pool({ nivel: "territorial", territorio: { id: 4, nome: "Sertão do Apodi", estados: ["RN"] } });

function renderizar(pools: PoolOrcamentoApi[], comMeta = false) {
  const onSelect = vi.fn();
  render(<MatrizOrcamento grupos={montarMatriz(pools)} comMeta={comMeta} onSelect={onSelect} />);
  return onSelect;
}

describe("MatrizOrcamento (#398)", () => {
  it("UGP: um bloco por rubrica com Nacional, estado e território, cada um com o seu nível", () => {
    renderizar([nacional, estadual, territorial]);
    const bloco = screen.getByTestId("orcamento-rubrica-diarias");
    expect(within(bloco).getByText("Diárias")).toBeTruthy();
    const linhas = within(bloco).getAllByTestId(/^orcamento-linha-/);
    expect(linhas.map((l) => l.getAttribute("data-nivel-pool"))).toEqual(["nacional", "estadual", "territorial"]);
    expect(linhas[0].textContent).toContain("Nacional");
    expect(linhas[0].textContent).toContain("R$ 100.000,00");
    expect(linhas[1].textContent).toContain("Rio Grande do Norte");
    expect(linhas[2].textContent).toContain("Sertão do Apodi");
  });

  it("Articulador: o estado e os territórios dele, sem a raiz nacional se ela não vier", () => {
    renderizar([estadual, territorial]);
    const linhas = screen.getAllByTestId(/^orcamento-linha-/);
    expect(linhas.map((l) => l.getAttribute("data-nivel-pool"))).toEqual(["estadual", "territorial"]);
  });

  it("ADT: só o pool do território, e o detalhar devolve o pool clicado", () => {
    const onSelect = renderizar([territorial]);
    expect(screen.getAllByTestId(/^orcamento-linha-/)).toHaveLength(1);
    fireEvent.click(screen.getByTestId(`orcamento-detalhar-${territorial.id}`));
    expect(onSelect.mock.calls[0][0].linha.id).toBe(territorial.id);
  });

  it("com a Meta escolhida, a coluna Executado mostra o executado na Meta", () => {
    renderizar([territorial], true);
    expect(screen.getByText("Executado na Meta")).toBeTruthy();
    const linha = screen.getByTestId(`orcamento-linha-${territorial.id}`);
    expect(linha.textContent).toContain("R$ 300,00");
    expect(linha.textContent).not.toContain("R$ 1.000,00");
  });
});
