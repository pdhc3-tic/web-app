import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { ImpactoDesativacao, UserListItem } from "@/app/lib/users";
import { AVISO_IMPACTO_MUDOU, DesativarUsuarioDialog } from "./DesativarUsuarioDialog";

/** #406 — o diálogo lista o impacto e exige confirmação explícita antes de desativar. */

const api = vi.hoisted(() => ({ impacto: vi.fn(), desativar: vi.fn() }));

vi.mock("@/app/lib/users", async (original) => ({
  ...(await original<typeof import("@/app/lib/users")>()),
  fetchImpactoDesativacao: api.impacto,
  desativarUsuario: api.desativar,
}));

vi.mock("@/app/providers/SgpChoicesProvider", () => ({
  useRotuloChoice: () => (valor: string) => (valor === "submetida" ? "Submetida" : valor),
}));

const USUARIO = { id: 7, nome_completo: "Ewerton Bandeira", email: "ewerton@demo.local", ativo: true } as UserListItem;

const IMPACTO: ImpactoDesativacao = {
  demandas: [
    { id: 41, titulo: "Van do intercâmbio", status: "submetida", saldo_liberado: "700.00" },
    { id: 42, titulo: "Diárias da oficina", status: "rascunho", saldo_liberado: "0.00" },
  ],
  saldo_por_rubrica: [{ rubrica_id: 3, rubrica_nome: "Locação de veículo", valor: "700.00" }],
  saldo_liberado: "700.00",
};

function montar(onDesativado = vi.fn(), onClose = vi.fn()) {
  render(<DesativarUsuarioDialog usuario={USUARIO} onClose={onClose} onDesativado={onDesativado} />);
  return { onDesativado, onClose };
}

const confirmar = () => screen.getByTestId("desativar-confirmar") as HTMLButtonElement;

beforeEach(() => {
  api.impacto.mockReset();
  api.desativar.mockReset();
});

describe("DesativarUsuarioDialog (#406)", () => {
  it("lista as demandas que serão canceladas e o saldo que será liberado", async () => {
    api.impacto.mockResolvedValue(IMPACTO);
    montar();

    const demanda = await screen.findByTestId("impacto-demanda-41");
    expect(api.impacto).toHaveBeenCalledWith(7, expect.anything());
    expect(demanda.textContent).toContain("Van do intercâmbio");
    expect(demanda.textContent).toContain("Submetida");
    expect(demanda.textContent).toContain("700,00");
    expect(screen.getByTestId("impacto-demanda-42").textContent).toContain("Diárias da oficina");
    expect(screen.getByTestId("impacto-rubrica-3").textContent).toContain("Locação de veículo");
    expect(screen.getByTestId("impacto-total").textContent).toContain("700,00");
  });

  it("só libera o botão depois da confirmação explícita", async () => {
    let entregar: (impacto: ImpactoDesativacao) => void = () => {};
    api.impacto.mockReturnValue(new Promise<ImpactoDesativacao>((resolve) => (entregar = resolve)));
    api.desativar.mockResolvedValue(undefined);
    const { onDesativado } = montar();

    // O SlideOver monta o conteúdo num efeito. Enquanto o impacto carrega,
    // não há como confirmar.
    await screen.findByTestId("desativar-impacto-carregando");
    expect(confirmar().disabled).toBe(true);
    expect(screen.queryByTestId("desativar-ciente")).toBeNull();

    entregar(IMPACTO);
    await screen.findByTestId("desativar-impacto");
    expect(confirmar().disabled).toBe(true);

    fireEvent.click(confirmar());
    expect(api.desativar).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("desativar-ciente"));
    expect(confirmar().disabled).toBe(false);
    fireEvent.click(confirmar());

    await waitFor(() => expect(onDesativado).toHaveBeenCalledWith(USUARIO));
    expect(api.desativar).toHaveBeenCalledWith(7);
  });

  it("sem demanda a cancelar, avisa que não há impacto e ainda pede a confirmação", async () => {
    api.impacto.mockResolvedValue({ demandas: [], saldo_por_rubrica: [], saldo_liberado: "0.00" });
    montar();

    expect((await screen.findByTestId("desativar-sem-impacto")).textContent).toContain("Nenhuma demanda será cancelada");
    expect(screen.queryByTestId("desativar-impacto")).toBeNull();
    expect(confirmar().disabled).toBe(true);
    fireEvent.click(screen.getByTestId("desativar-ciente"));
    expect(confirmar().disabled).toBe(false);
  });

  it("se o impacto não carrega, não deixa desativar às cegas", async () => {
    api.impacto.mockRejectedValue(new ApiError(500, { code: "error", message: "Falha ao calcular." }));
    montar();

    expect((await screen.findByTestId("desativar-impacto-erro")).textContent).toContain("Falha ao calcular.");
    expect(screen.queryByTestId("desativar-ciente")).toBeNull();
    expect(confirmar().disabled).toBe(true);
  });

  it("erro na desativação aparece no diálogo e ele continua aberto", async () => {
    api.impacto.mockResolvedValue(IMPACTO);
    api.desativar.mockRejectedValue(new ApiError(400, { code: "error", message: "Não foi possível cancelar a demanda 41." }));
    const { onDesativado } = montar();

    await screen.findByTestId("desativar-impacto");
    fireEvent.click(screen.getByTestId("desativar-ciente"));
    fireEvent.click(confirmar());

    expect((await screen.findByTestId("desativar-erro")).textContent).toBe("Não foi possível cancelar a demanda 41.");
    expect(onDesativado).not.toHaveBeenCalled();
  });

  it("se as demandas mudaram no meio do caminho, recalcula o impacto e pede a confirmação de novo", async () => {
    // A 41 foi autorizada depois da leitura: o backend desfaz a desativação.
    const depois: ImpactoDesativacao = {
      demandas: [IMPACTO.demandas[1]],
      saldo_por_rubrica: [],
      saldo_liberado: "0.00",
    };
    api.impacto.mockResolvedValueOnce(IMPACTO).mockResolvedValueOnce(depois);
    api.desativar.mockRejectedValue(
      // Como o backend responde: `{status: [msg], code}`, que a normalização vira `validation_error`.
      new ApiError(
        400,
        { code: "validation_error", message: "Transição inválida." },
        { status: ["Transição inválida."], code: "INVALID_TRANSITION" },
      ),
    );
    const { onDesativado } = montar();

    await screen.findByTestId("impacto-demanda-41");
    fireEvent.click(screen.getByTestId("desativar-ciente"));
    fireEvent.click(confirmar());

    await waitFor(() => expect(screen.queryByTestId("impacto-demanda-41")).toBeNull());
    expect(await screen.findByTestId("impacto-demanda-42")).toBeTruthy();
    expect(api.impacto).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("desativar-erro").textContent).toBe(AVISO_IMPACTO_MUDOU);
    expect((screen.getByTestId("desativar-ciente") as HTMLInputElement).checked).toBe(false);
    expect(confirmar().disabled).toBe(true);
    expect(onDesativado).not.toHaveBeenCalled();
  });
});
