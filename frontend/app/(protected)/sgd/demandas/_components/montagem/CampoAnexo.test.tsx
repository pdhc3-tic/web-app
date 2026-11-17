import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  configDoSchema,
  montarCamposJson,
  validarCampos,
  type ValoresCampos,
} from "@/app/lib/camposSolicitacao";
import type { SolicitacaoDemanda } from "@/app/lib/demandas";
import type { SchemaCampos } from "@/app/lib/tiposSolicitacao";
import { AnexosSolicitacao } from "./AnexosSolicitacao";
import type { ContextoAnexo } from "./CampoAnexo";
import { CampoDinamico } from "./CampoDinamico";

/**
 * #365 — campo de anexo do catálogo (PR #422): `{"type": "integer", "format":
 * "anexo"}`, ou um `array` deles. O arquivo sobe pelo fluxo de documentos da
 * demanda com `tipo="anexo"`, e o campo guarda o id do documento.
 */

const enviar = vi.fn();
const abrir = vi.fn();
vi.mock("@/app/lib/solicitacoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/solicitacoes")>()),
  enviarDocumentoDemanda: (...args: unknown[]) => enviar(...args),
  abrirDocumentoDemanda: (...args: unknown[]) => abrir(...args),
}));
vi.mock("@/app/providers/SgpChoicesProvider", () => ({ useSgpChoices: () => ({}) }));

const SCHEMA: SchemaCampos = {
  type: "object",
  required: ["reserva"],
  properties: {
    reserva: { type: "integer", format: "anexo", title: "Comprovante de reserva", "x-ordem": 1 },
    fotos: {
      type: "array",
      items: { type: "integer", format: "anexo" },
      title: "Fotos do local",
      "x-ordem": 2,
    },
  },
};
vi.mock("@/app/lib/hooks/useTiposSolicitacao", () => ({
  useTiposSolicitacao: () => ({ data: [{ slug: "hospedagem", schema_campos: SCHEMA }] }),
}));

const config = configDoSchema(SCHEMA);
const pdf = (nome: string) => new File(["%PDF-1.4"], nome, { type: "application/pdf" });
const valoresNaTela = (): ValoresCampos => JSON.parse(screen.getByTestId("valores").textContent ?? "{}");

function Formulario({ contexto, inicial = {} }: { contexto?: Partial<ContextoAnexo>; inicial?: ValoresCampos }) {
  const [valores, setValores] = useState<ValoresCampos>(inicial);
  const [nomes, setNomes] = useState<Record<number, string>>(contexto?.nomes ?? {});
  const ctx: ContextoAnexo | undefined = contexto && {
    demandaId: 7,
    nomes,
    onEnviado: (doc) => {
      setNomes((n) => ({ ...n, [doc.id]: doc.nome_original }));
      contexto.onEnviado?.(doc);
    },
    onRetirado: (id) => contexto.onRetirado?.(id),
  };
  return (
    <div>
      {config.campos.map((campo) => (
        <CampoDinamico
          key={campo.chave}
          campo={campo}
          valor={valores[campo.chave] ?? ""}
          onChange={(v) => setValores((atual) => ({ ...atual, [campo.chave]: v }))}
          anexo={ctx}
        />
      ))}
      <output data-testid="valores">{JSON.stringify(valores)}</output>
    </div>
  );
}

const arquivoDo = (chave: string) => screen.getByTestId(`campo-${chave}`).querySelector("input[type=file]") as HTMLInputElement;

beforeEach(() => {
  enviar.mockReset();
  abrir.mockReset();
});

describe("configDoSchema — anexo (#365)", () => {
  it("o integer com format anexo é um arquivo, não um número; o array deles aceita vários", () => {
    const [reserva, fotos] = config.campos;
    expect(reserva).toMatchObject({ chave: "reserva", tipo: "anexo", obrigatorio: true });
    expect(reserva.multiplo).toBeFalsy();
    expect(fotos).toMatchObject({ chave: "fotos", tipo: "anexo", multiplo: true, obrigatorio: false });
  });

  it("obrigatório vazio é erro; vazio não vai no campos_json", () => {
    expect(validarCampos("hospedagem", config, {})).toEqual({ reserva: "Campo obrigatório." });
    expect(montarCamposJson(config, {})).toEqual({});
  });
});

describe("CampoAnexo (#365)", () => {
  it("envia o PDF como anexo da demanda e guarda o id: um no campo simples, a lista no de vários", async () => {
    const onEnviado = vi.fn();
    enviar
      .mockResolvedValueOnce({ id: 41, nome_original: "reserva.pdf" })
      .mockResolvedValueOnce({ id: 42, nome_original: "frente.pdf" })
      .mockResolvedValueOnce({ id: 43, nome_original: "fundos.pdf" });
    render(<Formulario contexto={{ onEnviado }} />);

    fireEvent.change(arquivoDo("reserva"), { target: { files: [pdf("reserva.pdf")] } });
    await screen.findByText("reserva.pdf");
    expect(enviar).toHaveBeenCalledWith(7, expect.any(File), { tipo: "anexo", descricao: "", fornecedor: "" }, expect.any(Function));
    expect(onEnviado).toHaveBeenCalledWith(expect.objectContaining({ id: 41 }));
    // Campo de um arquivo, já preenchido: não oferece outro envio.
    expect(arquivoDo("reserva")).toBeNull();

    fireEvent.change(arquivoDo("fotos"), { target: { files: [pdf("frente.pdf")] } });
    await screen.findByText("frente.pdf");
    fireEvent.change(arquivoDo("fotos"), { target: { files: [pdf("fundos.pdf")] } });
    await screen.findByText("fundos.pdf");

    expect(montarCamposJson(config, valoresNaTela())).toEqual({ reserva: 41, fotos: [42, 43] });
  });

  it("recusa o que não é PDF sem enviar", () => {
    render(<Formulario contexto={{}} />);
    fireEvent.change(arquivoDo("reserva"), { target: { files: [new File(["x"], "foto.jpg", { type: "image/jpeg" })] } });
    expect(screen.getByText("Apenas PDF é aceito.")).toBeTruthy();
    expect(enviar).not.toHaveBeenCalled();
  });

  it("mostra o erro do backend no campo, sem guardar nada", async () => {
    const { ApiError } = await import("@/app/lib/api");
    enviar.mockRejectedValueOnce(new ApiError(400, { code: "invalid", message: "Limite de 10 documentos por demanda atingido." }));
    render(<Formulario contexto={{}} />);
    fireEvent.change(arquivoDo("reserva"), { target: { files: [pdf("reserva.pdf")] } });
    await screen.findByText("Limite de 10 documentos por demanda atingido.");
    expect(valoresNaTela()).toEqual({});
  });

  it("retirar o arquivo limpa o campo e avisa o formulário; o nome salvo vem do contexto", () => {
    const onRetirado = vi.fn();
    render(<Formulario contexto={{ onRetirado, nomes: { 41: "reserva.pdf" } }} inicial={{ reserva: "41" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Retirar reserva.pdf" }));
    expect(onRetirado).toHaveBeenCalledWith(41);
    expect(valoresNaTela()).toEqual({ reserva: "" });
    expect(arquivoDo("reserva")).not.toBeNull();
  });

  it("sem demanda (pré-visualização do catálogo), o campo aparece desabilitado", () => {
    render(<Formulario />);
    expect(arquivoDo("reserva").disabled).toBe(true);
    expect(screen.getAllByText(/O arquivo é enviado ao preencher a solicitação na demanda/).length).toBe(2);
  });
});

describe("AnexosSolicitacao (#365)", () => {
  const solicitacao = (anexos: SolicitacaoDemanda["anexos"]) =>
    ({ id: 3, demanda: 7, tipo: "hospedagem", anexos }) as SolicitacaoDemanda;

  it("lista os arquivos com o nome do campo do catálogo e abre pelo id", () => {
    render(
      <AnexosSolicitacao
        solicitacao={solicitacao({
          reserva: { id: 41, nome_original: "reserva.pdf", download: "/x" },
          fotos: [
            { id: 42, nome_original: "frente.pdf", download: "/y" },
            { id: 43, nome_original: "fundos.pdf", download: "/z" },
          ],
        })}
      />,
    );
    const bloco = screen.getByTestId("anexos-solicitacao-3");
    expect(bloco.textContent).toContain("Comprovante de reserva:");
    expect(bloco.textContent).toContain("Fotos do local:");
    fireEvent.click(screen.getByText("fundos.pdf"));
    expect(abrir).toHaveBeenCalledWith(7, 43);
  });

  it("não aparece num tipo sem anexo, nem com o campo vazio", async () => {
    const { container, rerender } = render(<AnexosSolicitacao solicitacao={solicitacao({})} />);
    expect(container.textContent).toBe("");
    rerender(<AnexosSolicitacao solicitacao={solicitacao({ reserva: null, fotos: [] })} />);
    await waitFor(() => expect(container.textContent).toBe(""));
  });
});
