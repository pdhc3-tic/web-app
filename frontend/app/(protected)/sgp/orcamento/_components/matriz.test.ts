import { describe, expect, it } from "vitest";
import type { PoolOrcamentoApi } from "@/app/lib/orcamento";
import { montarMatriz } from "./matriz";

/** #398 — a lista plana do painel vira a matriz Rubrica × Nível em árvore. */

const DIARIAS = { id: 1, slug: "diarias", nome: "Diárias" };
const PASSAGENS = { id: 2, slug: "passagens-aereas", nome: "Passagens Aéreas" };

let proximoId = 1;
function pool(p: Partial<PoolOrcamentoApi> & Pick<PoolOrcamentoApi, "nivel">): PoolOrcamentoApi {
  return {
    id: proximoId++,
    rubrica: DIARIAS,
    estado: null,
    territorio: null,
    reserva_ugp: false,
    valor_aprovado: "1000.00",
    valor_distribuido: "0.00",
    valor_comprometido: "0.00",
    valor_executado: "0.00",
    saldo_disponivel: "1000.00",
    saldo_pool: "1000.00",
    semaforo: "verde",
    alerta_80: false,
    limiares_semaforo: { amarelo: 70, vermelho: 90 },
    ...p,
  };
}

const RN = { id: 20, sigla: "RN", nome: "Rio Grande do Norte" };
const PB = { id: 15, sigla: "PB", nome: "Paraíba" };
const nacional = () => pool({ nivel: "nacional" });
const estado = (e: typeof RN) => pool({ nivel: "estadual", estado: e });
const territorio = (id: number, nome: string, estados: string[]) =>
  pool({ nivel: "territorial", territorio: { id, nome, estados } });

const nomes = (celulas: ReturnType<typeof montarMatriz>[number]["celulas"]) =>
  celulas.map((c) => `${c.profundidade}:${c.linha.estado?.sigla ?? c.linha.territorio?.nome ?? "Nacional"}`);

describe("montarMatriz (#398)", () => {
  it("UGP: Nacional → estados por nome → os territórios de cada estado", () => {
    // A ordem do backend: rubrica, nível, sigla, nome — todos os estados antes dos territórios.
    const [diarias] = montarMatriz([
      nacional(),
      estado(PB),
      estado(RN),
      territorio(1, "Sertão do Apodi", ["RN"]),
      territorio(2, "Borborema", ["PB"]),
      territorio(3, "Açu-Mossoró", ["RN"]),
    ]);
    expect(diarias.rubrica.slug).toBe("diarias");
    expect(nomes(diarias.celulas)).toEqual([
      "0:Nacional",
      "1:PB",
      "2:Borborema",
      "1:RN",
      "2:Açu-Mossoró",
      "2:Sertão do Apodi",
    ]);
  });

  it("um bloco por rubrica, na ordem em que o backend as devolve", () => {
    const grupos = montarMatriz([nacional(), pool({ nivel: "nacional", rubrica: PASSAGENS })]);
    expect(grupos.map((g) => g.rubrica.slug)).toEqual(["diarias", "passagens-aereas"]);
  });

  it("Articulador: território de dois estados entra sob o primeiro que está no recorte", () => {
    const [diarias] = montarMatriz([nacional(), estado(RN), territorio(9, "Seridó", ["PB", "RN"])]);
    expect(nomes(diarias.celulas)).toEqual(["0:Nacional", "1:RN", "2:Seridó"]);
  });

  it("ADT: só o território, sem raiz nem estado, fica no primeiro nível", () => {
    const [diarias] = montarMatriz([territorio(1, "Sertão do Apodi", ["RN"])]);
    expect(nomes(diarias.celulas)).toEqual(["0:Sertão do Apodi"]);
  });

  it("deriva o semáforo, o percentual e o vazio sem recalcular o backend", () => {
    const [diarias] = montarMatriz([
      pool({ nivel: "nacional", valor_aprovado: "1000.00", valor_comprometido: "950.00", semaforo: "vermelho" }),
      estado({ ...RN }),
    ]);
    const [raiz] = diarias.celulas;
    expect(raiz.nivelSemaforo).toBe("vermelho");
    expect(raiz.percentual).toBeCloseTo(95);
    expect(raiz.vazia).toBe(false);

    const [zerado] = montarMatriz([
      pool({ nivel: "nacional", valor_aprovado: "0.00", saldo_disponivel: "0.00", semaforo: "verde" }),
    ])[0].celulas;
    expect(zerado.nivelSemaforo).toBe("sem-dado");
    expect(zerado.vazia).toBe(true);
  });
});
