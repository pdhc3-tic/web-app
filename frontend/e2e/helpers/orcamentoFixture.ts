import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture de orçamento para o E2E do Painel de Orçamento (§5.3.3) e do saldo
 * por rubrica do ADT (#232), sobre o orçamento por pool (#398).
 *
 * O `seed_demo` não monta o orçamento nacional nem os estaduais. A fixture
 * fotografa o orçamento, ajusta (ou cria) estes pools com valores
 * determinísticos e, no teardown, restaura a fotografia (`orcamentoE2E.ts`):
 *
 * - Diárias, nacional: 100.000 aprovado, 95.000 comprometido → 95%, vermelho;
 * - Passagens Aéreas, nacional: 50.000 aprovado, 10.000 comprometido → verde;
 * - Passagens Aéreas, estadual de PE: 12.000, distinto do nacional de propósito;
 * - Diárias, territorial do ADT dos E2E (Marina): 7.000 aprovado, 1.400
 *   comprometido, 700 executado → 4.900 de saldo.
 *
 * O território da Marina é sorteado pelo `seed_demo`; a fixture o descobre.
 * Roda como `postgres`: a restauração desliga o trigger do ledger na sessão.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/** E-mail do ADT/ACR dos E2E — o mesmo `semPermissao` de helpers/users.ts. */
const EMAIL_ADT = process.env.E2E_LEITOR_EMAIL ?? "marina.albuquerque@demo.pdhc.local";

/** Número da Meta usada no filtro de executado (relatório). */
export const META_COM_ORCAMENTO = 1;

/** Rubrica levada a 95% de comprometido — vermelha com o limiar padrão de 90%. */
export const RUBRICA_CRITICA = { slug: "diarias", nome: "Diárias" };

/** Rubrica mantida bem abaixo do limiar, para provar que nem tudo alerta. */
export const RUBRICA_TRANQUILA = { slug: "passagens-aereas", nome: "Passagens Aéreas" };

/** Rubrica sem pool nenhum na fixture: o caso do estado vazio. */
export const RUBRICA_SEM_POOL = { slug: "equipamentos-capital", nome: "Equipamentos/Capital" };

/** Estado do drill-down estadual — PE existe em qualquer re-seed. */
export const ESTADO_DRILL = { sigla: "PE", nome: "Pernambuco" };

export type OrcamentoFixture = {
  territorioAdt: string;
  territorioAdtId: number;
  metaId: number;
  /** Ids dos pools da fixture. */
  pools: {
    diariasNacional: number;
    passagensNacional: number;
    passagensPE: number;
    diariasTerritorio: number;
  };
};

const MARCADOR = "PDHC_E2E_ORCAMENTO";
const FOTO = "orcamento-painel";

const SETUP_SCRIPT = `${ORCAMENTO_E2E_PY}
import json
from apps.core.models import State
from apps.core.models.user_profile import UserProfile
from apps.sgp.budget.models import BudgetRubrica
from apps.sgp.models import WorkPlanMeta

fotografar("${FOTO}")
perfil = (
    UserProfile.objects.select_related("territorio")
    .filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True)
    .first()
)
if perfil is None:
    raise RuntimeError("ADT dos E2E sem territorio: rode manage.py seed_demo")
territorio = perfil.territorio
diarias = BudgetRubrica.objects.get(slug="${RUBRICA_CRITICA.slug}")
passagens = BudgetRubrica.objects.get(slug="${RUBRICA_TRANQUILA.slug}")
pe = State.objects.get(sigla="${ESTADO_DRILL.sigla}")

pools = {
    "diariasNacional": definir_pool(diarias, "nacional", "100000.00", comprometido="95000.00", executado="5000.00").pk,
    "passagensNacional": definir_pool(passagens, "nacional", "50000.00", comprometido="10000.00", executado="2500.00").pk,
    "passagensPE": definir_pool(passagens, "estadual", "12000.00", estado=pe, comprometido="3000.00", executado="500.00").pk,
    "diariasTerritorio": definir_pool(
        diarias, "territorial", "7000.00", territorio_id=territorio.pk, comprometido="1400.00", executado="700.00",
    ).pk,
}
print("${MARCADOR}_SETUP " + json.dumps({
    "territorioAdt": territorio.nome,
    "territorioAdtId": territorio.pk,
    "metaId": WorkPlanMeta.objects.get(numero=${META_COM_ORCAMENTO}).pk,
    "pools": pools,
}))
`;

const TEARDOWN_SCRIPT = `${ORCAMENTO_E2E_PY}
restaurar("${FOTO}")
print("${MARCADOR}_TEARDOWN_OK")
`;

/** Como `postgres`, como as fixtures do SGD: a restauração precisa do superusuário. */
function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "backend",
      "sh",
      "-c",
      'DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD python manage.py shell -c "$1"',
      "sh",
      script,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Ajusta os pools e devolve os ids e o território do ADT descoberto no banco. */
export function criarOrcamentoFixture(): OrcamentoFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const marca = `${MARCADOR}_SETUP `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) throw new Error(`Falha ao criar a fixture de orçamento:\n${saida}`);
  return JSON.parse(linha.slice(marca.length)) as OrcamentoFixture;
}

/** Devolve o orçamento à fotografia do setup. */
export function removerOrcamentoFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture de orçamento:\n${saida}`);
  }
}

/**
 * Ajusta um pool extra dentro da mesma fotografia (a spec do saldo usa para o
 * saldo negativo). Some no teardown da fixture.
 */
export function definirPoolDoAdt(rubricaSlug: string, alocado: string, comprometido: string, executado: string): void {
  const saida = djangoShell(`${ORCAMENTO_E2E_PY}
from apps.core.models.user_profile import UserProfile
from apps.sgp.budget.models import BudgetRubrica

perfil = (
    UserProfile.objects.filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True).first()
)
definir_pool(
    BudgetRubrica.objects.get(slug="${rubricaSlug}"), "territorial", "${alocado}",
    territorio_id=perfil.territorio_id, comprometido="${comprometido}", executado="${executado}",
)
print("${MARCADOR}_POOL_OK")
`);
  if (!saida.includes(`${MARCADOR}_POOL_OK`)) throw new Error(`Falha ao ajustar o pool do ADT:\n${saida}`);
}

/** Slugs das rubricas com pool no território do ADT dos E2E, lidos do banco. */
export function rubricasComPoolDoAdt(): string[] {
  const saida = djangoShell(`
import json
from apps.core.models.user_profile import UserProfile
from apps.sgp.budget.models import BudgetPool

perfil = (
    UserProfile.objects.filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True).first()
)
slugs = BudgetPool.objects.filter(nivel="territorial", territorio_id=perfil.territorio_id).values_list("rubrica__slug", flat=True)
print("${MARCADOR}_COM_POOL " + json.dumps(sorted(set(slugs))))
`);
  const marca = `${MARCADOR}_COM_POOL `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) throw new Error(`Falha ao ler os pools do ADT:\n${saida}`);
  return JSON.parse(linha.slice(marca.length)) as string[];
}

// ─── Vínculo do ADT com o território ────────────────────────────────────────

/**
 * Desfaz e refaz o vínculo do ADT dos E2E com o território dele.
 *
 * Existe para o teste do "usuário sem território" (Issue #232) poder exercer o
 * caminho REAL: `resolver_nivel_painel` só devolve 403 a quem de fato não tem
 * `UserProfile.territorio`. Enquanto o teste apenas esvaziava `territorios` na
 * resposta da sessão, o backend seguia respondendo 200 — o 403 nunca chegava à
 * página, e o estado vazio que o teste via era o do componente decidindo pela
 * sessão, não o da tela sobrevivendo à negativa da API.
 *
 * O território é devolvido para que o teste o reponha: perdê-lo quebraria todas
 * as outras specs do ADT, que dependem dele. Por isso o `revincular` roda num
 * `finally`, e não no corpo do teste — uma asserção que falha no meio não pode
 * deixar o banco de demonstração sem o vínculo.
 */
export function desvincularTerritorioDoAdt(): number {
  const saida = djangoShell(`
from apps.core.models.user_profile import UserProfile

perfil = (
    UserProfile.objects
    .filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True)
    .first()
)
if perfil is None:
    raise RuntimeError("ADT dos E2E sem territorio: rode manage.py seed_demo")

territorio_id = perfil.territorio_id
perfil.territorio = None
perfil.save(update_fields=["territorio"])

print("${MARCADOR}_DESVINCULADO " + str(territorio_id))
`);
  const marca = `${MARCADOR}_DESVINCULADO `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) {
    throw new Error(`Falha ao desvincular o território do ADT:\n${saida}`);
  }
  return Number(linha.slice(marca.length).trim());
}

/** Repõe o vínculo. Idempotente: repetir com o mesmo id não faz mal. */
export function revincularTerritorioDoAdt(territorioId: number): void {
  const saida = djangoShell(`
from apps.core.models.user_profile import UserProfile

atualizados = (
    UserProfile.objects
    .filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .update(territorio_id=${territorioId})
)
if not atualizados:
    raise RuntimeError("Perfil ADT dos E2E nao encontrado para revincular")

print("${MARCADOR}_REVINCULADO_OK")
`);
  if (!saida.includes(`${MARCADOR}_REVINCULADO_OK`)) {
    throw new Error(`Falha ao repor o território do ADT:\n${saida}`);
  }
}
