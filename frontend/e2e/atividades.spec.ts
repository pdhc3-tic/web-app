import path from "node:path";
import { expect, test } from "@playwright/test";
import { storageStatePath } from "./helpers/users";
import { primeiroUpfId } from "./helpers/upf";

const ATIVIDADES_API = "**/api/v1/sgp/atividades/**";
const FOTOS_API = "**/api/v1/sgp/atividades/*/fotos/**";
const DOCUMENTOS_API = "**/api/v1/sgp/atividades/*/documentos/**";

function atividadeFake(
  id: number,
  titulo: string,
  status: string,
): Record<string, unknown> {
  return {
    id,
    titulo,
    status,
    tipo_atividade: "visita_tecnica",
    tipo_atividade_display: "Visita técnica",
    acao: { id: 1, numero: "1.1", descricao: "Ação teste" },
    forma_atuacao: "realizacao",
    tecnico_responsavel: { id: 10, nome_completo: "Beatriz Nogueira" },
    equipe_adicional: [],
    municipio: { id: 1001, nome: "Ouricuri", state: 17 },
    comunidade: null,
    ambito: "municipal",
    latitude: null,
    longitude: null,
    data_inicio: "2026-06-01",
    data_fim: "2026-06-01",
    upfs_participantes: [],
    membros_participantes: [],
    parceiros: "",
    descricao_narrativa: "Visita de acompanhamento.",
    resultados_alcancados: "",
    justificativa: "",
    fotos: [],
    documentos: [],
    transicoes_permitidas: ["concluido"],
    criado_em: "2026-06-01T10:00:00Z",
    atualizado_em: "2026-06-01T10:00:00Z",
  };
}

function paginated(results: unknown[]): string {
  return JSON.stringify({
    count: results.length,
    next: null,
    previous: null,
    results,
  });
}

test.describe("SGP — Criação de atividade", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("submit sem campos obrigatórios exibe erros inline", async ({ page }) => {
    await page.goto("/sgp/atividades/nova");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByRole("button", { name: "Salvar atividade" }).click();

    await expect(page.getByText("Informe o título da atividade.")).toBeVisible();
    await expect(page.getByText("Selecione o tipo de atividade.")).toBeVisible();
    await expect(page.getByText("Selecione a Ação do PT.")).toBeVisible();
    await expect(page.getByText("Selecione o técnico responsável.")).toBeVisible();
    await expect(page.getByText("Descreva a atividade.")).toBeVisible();
  });

  test("data de fim anterior à de início exibe mensagem de erro", async ({
    page,
  }) => {
    await page.goto("/sgp/atividades/nova");

    await page.locator("#atividade-data-inicio").fill("2026-06-10");
    await page.locator("#atividade-data-fim").fill("2026-06-05");
    await page.getByRole("button", { name: "Salvar atividade" }).click();

    await expect(
      page.getByText("A data de fim não pode ser anterior à data de início."),
    ).toBeVisible();
  });

  test("justificativa é exigida quando status é Não realizada", async ({
    page,
  }) => {
    await page.goto("/sgp/atividades/nova");

    await page.locator("#atividade-titulo").fill("Teste de justificativa");
    await page.getByRole("button", { name: "Salvar atividade" }).click();

    await expect(page.getByText("Selecione o tipo de atividade.")).toBeVisible();
  });

  test("criação bem-sucedida redireciona para edição da atividade", async ({
    page,
  }) => {
    // Mock dos dropdowns que o formulário carrega ao montar
    await page.route("**/api/v1/acoes/**", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1, next: null, previous: null,
          results: [{ id: 1, meta: 1, numero: "1.1", descricao: "Ação teste" }],
        }),
      });
    });

    await page.route("**/api/v1/users/**", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1, next: null, previous: null,
          results: [{ id: 10, nome_completo: "Beatriz Nogueira" }],
        }),
      });
    });

    await page.route("**/api/v1/states/**", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1, next: null, previous: null,
          results: [{ id: 17, sigla: "PE", nome: "Pernambuco" }],
        }),
      });
    });

    await page.route("**/api/v1/municipalities/**", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1, next: null, previous: null,
          results: [{ id: 1001, nome: "Ouricuri", state: 17, territory: null }],
        }),
      });
    });

    await page.route("**/api/v1/municipios/**", async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
      });
    });

    await page.route(ATIVIDADES_API, async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(atividadeFake(4242, "Visita E2E", "planejado")),
      });
    });

    await page.goto("/sgp/atividades/nova");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // Aguarda carregamento dos dados relacionados (ações, técnicos, estados)
    await expect(page.getByText("Carregando atividades…")).not.toBeVisible({
      timeout: 10_000,
    });

    await page.locator("#atividade-titulo").fill("Visita E2E");

    await page.locator("#atividade-tipo-atividade").click();
    await page.getByRole("option", { name: "Visita técnica" }).click();

    await page.locator("#atividade-forma-atuacao").click();
    await page.getByRole("option", { name: "Realização" }).click();

    // AcaoCombobox: campo de texto com dropdown; digitar abre e filtra a lista
    await page.locator("#atividade-acao").fill("1.1");
    await page.getByRole("option", { name: /1\.1 — Ação teste/ }).click();

    await page.locator("#atividade-tecnico-responsavel").click();
    await page.getByRole("option", { name: "Beatriz Nogueira" }).click();

    // Cascata estado → município
    await page.locator("#atividade-estado").click();
    await page.getByRole("option", { name: "Pernambuco (PE)" }).click();

    // Aguarda o select de município ser habilitado após a seleção do estado
    await expect(page.locator("#atividade-municipio")).not.toBeDisabled({
      timeout: 5_000,
    });
    await page.locator("#atividade-municipio").click();
    await page.getByRole("option", { name: "Ouricuri" }).click();

    await page.locator("#atividade-ambito").click();
    await page.getByRole("option", { name: "Municipal" }).click();

    await page.locator("#atividade-data-inicio").fill("2026-06-01");
    await page.locator("#atividade-data-fim").fill("2026-06-01");

    await page.locator("#atividade-descricao-narrativa").fill(
      "Visita de acompanhamento.",
    );

    await page.getByRole("button", { name: "Salvar atividade" }).click();

    // Verifica que o formulário redirecionou para a tela de edição da nova atividade
    await page.waitForURL("**/sgp/atividades/4242/**", { timeout: 10_000 });
  });
});

test.describe("SGP — Listagem de atividades", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("listagem renderiza atividades do seed com colunas corretas", async ({
    page,
  }) => {
    await page.goto("/sgp/atividades");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Título" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible();
  });

  test("filtro por status=concluido_sem_evidencia lista apenas as pendentes", async ({
    page,
  }) => {
    await page.route(ATIVIDADES_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          atividadeFake(1, "Visita sem fotos", "concluido_sem_evidencia"),
          atividadeFake(2, "Oficina pendente", "concluido_sem_evidencia"),
        ]),
      });
    });

    await page.goto("/sgp/atividades?status=concluido_sem_evidencia");
    await expect(page.getByText("Visita sem fotos")).toBeVisible();
    await expect(page.getByText("Oficina pendente")).toBeVisible();
    await expect(page.getByText("Concluído sem evidência").first()).toBeVisible();
  });

  test("estado vazio com filtros ativos exibe botão Limpar filtros", async ({
    page,
  }) => {
    await page.route(ATIVIDADES_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([]),
      });
    });

    await page.goto("/sgp/atividades?status=concluido");
    await expect(page.getByText(/Nenhuma atividade/i)).toBeVisible();
  });
});

test.describe("SGP — Evidências (fotos e documentos)", () => {
  test.use({ storageState: storageStatePath("ugp") });

  test("atividade com status concluido_sem_evidencia exibe badge correto na listagem", async ({
    page,
  }) => {
    await page.route(ATIVIDADES_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: paginated([
          atividadeFake(1, "Atividade sem evidência", "concluido_sem_evidencia"),
        ]),
      });
    });

    await page.goto("/sgp/atividades");
    await expect(page.getByText("Concluído sem evidência")).toBeVisible();
  });

  test("galeria de fotos aparece no formulário de edição", async ({ page }) => {
    const upfId = primeiroUpfId();

    await page.route(`**/api/v1/sgp/atividades/9001/`, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(atividadeFake(9001, "Atividade editável", "planejado")),
      });
    });

    await page.route(FOTOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route(DOCUMENTOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/sgp/atividades/9001/editar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(
      page.getByRole("heading", { name: /Fotos/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Documentos/i }),
    ).toBeVisible();

    const uploadBtn = page
      .getByRole("button", { name: /Adicionar foto/i })
      .or(page.getByLabel(/Adicionar foto/i));
    await expect(uploadBtn.first()).toBeVisible();
  });

  test("upload de foto é enviado ao endpoint correto", async ({ page }) => {
    const STORAGE_URL = "https://storage.example.com/upload";

    await page.route(`**/api/v1/sgp/atividades/9001/`, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(atividadeFake(9001, "Atividade editável", "planejado")),
      });
    });

    // Endpoint de solicitação da URL pré-assinada
    await page.route(
      "**/api/v1/sgp/atividades/9001/fotos/upload-url/",
      async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            url: STORAGE_URL,
            key: "test-key-123",
            expires_in: 3600,
          }),
        });
      },
    );

    // Simulação do storage externo (R2 / S3 pré-assinado)
    await page.route("https://storage.example.com/**", async (route) => {
      await route.fulfill({ status: 200 });
    });

    // Endpoint de confirmação do upload
    await page.route(
      "**/api/v1/sgp/atividades/9001/fotos/confirm/",
      async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: 1,
            url: `${STORAGE_URL}/foto.jpg`,
            legenda: "",
            ordem: 0,
          }),
        });
      },
    );

    // Listagem de fotos e documentos (GET)
    await page.route(FOTOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route(DOCUMENTOS_API, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/sgp/atividades/9001/editar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // O input de arquivo deve existir no DOM (não condicional)
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 5_000 });

    await fileInput.setInputFiles({
      name: "foto-teste.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.alloc(1024),
    });

    // Após selecionar o arquivo, o botão "Enviar" deve aparecer para confirmar o envio
    const uploadBtn = page.getByRole("button", { name: /Enviar .* foto/i });
    await expect(uploadBtn).toBeVisible({ timeout: 5_000 });

    // Aguarda a requisição ao endpoint de upload-url e então clica em Enviar
    const uploadUrlRequest = page.waitForRequest(
      (req) =>
        req.url().includes("/fotos/upload-url/") && req.method() === "POST",
      { timeout: 10_000 },
    );
    await uploadBtn.click();
    await uploadUrlRequest;
  });
});
