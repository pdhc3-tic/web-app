import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Perfil } from "@/app/lib/auth/types";
import { montarPerfisInput, opcoesDePerfil, validarNovoUsuario, type NovoUsuario } from "@/app/lib/users";
import { NovoUsuarioForm } from "./NovoUsuarioForm";

/** #405 — perfis principais (com território) e operacionais (com objeto) no cadastro de usuário. */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", async (original) => ({
  ...(await original<typeof import("@/app/lib/api")>()),
  apiClient: api.client,
}));

// O Select do design system abre uma lista própria; no teste, um <select> nativo.
vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    options,
    value,
    onChange,
  }: {
    id: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select data-testid={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" />
      {options
        .filter((o) => o.value !== "")
        .map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
    </select>
  ),
}));

const perfil = (id: number, slug: string, nome: string, categoria: Perfil["categoria"]): Perfil => ({
  id,
  slug,
  nome,
  categoria,
  descricao: "",
  ativo: true,
  criado_em: "2026-01-01T00:00:00Z",
});

const PERFIS: Perfil[] = [
  perfil(1, "adt-acr", "ADT / ACR", "principal"),
  perfil(2, "ugp", "UGP", "principal"),
  perfil(10, "coordenador-evento", "Coordenador de Evento", "operacional"),
  perfil(11, "gestor-edital", "Gestor de Edital", "operacional"),
];

const TERRITORIOS = [{ value: "5", label: "Território RN" }];

function montar(onCriado = vi.fn()) {
  render(
    <NovoUsuarioForm perfis={PERFIS} territoryOptions={TERRITORIOS} onCriado={onCriado} onCancelar={vi.fn()} />,
  );
  return onCriado;
}

const opcoesDe = (testId: string) =>
  Array.from((screen.getByTestId(testId) as HTMLSelectElement).options)
    .map((o) => o.textContent)
    .filter(Boolean);

beforeEach(() => api.client.mockReset());

describe("NovoUsuarioForm (#405)", () => {
  it("o seletor de objeto só aparece para perfil operacional", () => {
    montar();

    // A linha do perfil principal tem território e nenhum seletor de objeto.
    expect(screen.getByTestId("perfil-principal-0-territorio")).toBeTruthy();
    expect(screen.queryByTestId("perfil-operacional-0-objeto")).toBeNull();
    expect(screen.queryByLabelText(/número/)).toBeNull();

    fireEvent.click(screen.getByTestId("perfil-operacional-adicionar"));

    // A linha operacional tem o objeto e não tem território.
    expect(screen.getByTestId("perfil-operacional-0-objeto")).toBeTruthy();
    expect(screen.queryByTestId("perfil-operacional-0-territorio")).toBeNull();
    expect(screen.getByTestId("perfis-principais").querySelector('[data-testid$="-objeto"]')).toBeNull();
  });

  it("cada seção oferece só os perfis da sua categoria", () => {
    montar();
    fireEvent.click(screen.getByTestId("perfil-operacional-adicionar"));

    expect(opcoesDe("perfil-principal-0-perfil")).toEqual(["ADT / ACR", "UGP"]);
    expect(opcoesDe("perfil-operacional-0-perfil")).toEqual(["Coordenador de Evento", "Gestor de Edital"]);
  });

  it("o rótulo do objeto segue o tipo do perfil operacional", () => {
    montar();
    fireEvent.click(screen.getByTestId("perfil-operacional-adicionar"));
    expect(screen.getByLabelText(/Objeto de abrangência \(número\)/)).toBeTruthy();

    fireEvent.change(screen.getByTestId("perfil-operacional-0-perfil"), { target: { value: "10" } });
    expect(screen.getByLabelText(/Evento \(número\)/)).toBeTruthy();

    fireEvent.change(screen.getByTestId("perfil-operacional-0-perfil"), { target: { value: "11" } });
    expect(screen.getByLabelText(/Edital \(número\)/)).toBeTruthy();
  });

  it("não envia sem perfil principal nem com operacional sem objeto", () => {
    montar();
    fireEvent.change(screen.getByLabelText(/Nome completo/), { target: { value: "Maria Souza" } });
    fireEvent.change(screen.getByLabelText(/E-mail/), { target: { value: "maria@exemplo.org" } });
    fireEvent.click(screen.getByTestId("perfil-operacional-adicionar"));
    fireEvent.change(screen.getByTestId("perfil-operacional-0-perfil"), { target: { value: "10" } });
    fireEvent.click(screen.getByTestId("novo-usuario-salvar"));

    expect(screen.getByTestId("perfis-principais-erro").textContent).toBe("Escolha ao menos um perfil principal.");
    expect(screen.getByTestId("perfil-operacional-0-erro").textContent).toBe("Informe o número do evento.");
    expect(api.client).not.toHaveBeenCalled();
  });

  it("envia o principal com território e o operacional com o objeto do tipo certo", async () => {
    api.client.mockResolvedValue({ json: async () => ({ id: 9, nome_completo: "Maria Souza" }) });
    const onCriado = montar();

    fireEvent.change(screen.getByLabelText(/Nome completo/), { target: { value: "Maria Souza" } });
    fireEvent.change(screen.getByLabelText(/E-mail/), { target: { value: "maria@exemplo.org" } });
    fireEvent.change(screen.getByTestId("perfil-principal-0-perfil"), { target: { value: "1" } });
    fireEvent.change(screen.getByTestId("perfil-principal-0-territorio"), { target: { value: "5" } });
    fireEvent.click(screen.getByTestId("perfil-operacional-adicionar"));
    fireEvent.change(screen.getByTestId("perfil-operacional-0-perfil"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/Evento \(número\)/), { target: { value: "12" } });
    fireEvent.click(screen.getByTestId("novo-usuario-salvar"));

    await waitFor(() => expect(onCriado).toHaveBeenCalled());
    const [path, init] = api.client.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/users/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      nome_completo: "Maria Souza",
      email: "maria@exemplo.org",
      perfis_input: [
        { perfil_id: 1, territorio_id: 5, objeto_tipo: null, objeto_id: null },
        { perfil_id: 10, territorio_id: null, objeto_tipo: "evento", objeto_id: 12 },
      ],
    });
  });
});

describe("perfis no cadastro — regras", () => {
  const base: NovoUsuario = {
    nome: "Maria",
    email: "maria@exemplo.org",
    senha: "",
    principais: [{ perfil: "1", territorio: "" }],
    operacionais: [],
  };

  it("válido com um principal sem território (todos os territórios)", () => {
    expect(validarNovoUsuario(base, PERFIS)).toEqual({});
    expect(montarPerfisInput(base, PERFIS)).toEqual([
      { perfil_id: 1, territorio_id: null, objeto_tipo: null, objeto_id: null },
    ]);
  });

  it("recusa principal repetido no mesmo território e designação operacional repetida", () => {
    expect(
      validarNovoUsuario({ ...base, principais: [base.principais[0], { perfil: "1", territorio: "" }] }, PERFIS)
        .principais,
    ).toBe("O mesmo perfil está repetido no mesmo território.");
    expect(
      validarNovoUsuario(
        { ...base, operacionais: [{ perfil: "10", objetoId: "3" }, { perfil: "10", objetoId: "3" }] },
        PERFIS,
      ).operacionais,
    ).toEqual({ 1: "Este perfil já está designado a este objeto." });
  });

  it("recusa objeto que não é número inteiro positivo", () => {
    for (const objetoId of ["", "0", "-2", "1.5", "abc"]) {
      expect(
        validarNovoUsuario({ ...base, operacionais: [{ perfil: "11", objetoId }] }, PERFIS).operacionais,
      ).toEqual({ 0: "Informe o número do edital." });
    }
  });

  it("opcoesDePerfil recorta pela categoria, e perfil sem categoria conta como principal", () => {
    expect(opcoesDePerfil(PERFIS, "operacional").map((o) => o.value)).toEqual(["10", "11"]);
    expect(opcoesDePerfil(PERFIS, "").length).toBe(4);
    expect(opcoesDePerfil([{ ...PERFIS[0], categoria: undefined }], "principal").length).toBe(1);
  });
});
