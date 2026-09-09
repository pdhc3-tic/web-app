import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture de orçamento para o E2E do painel de §5.3.3.
 *
 * ─── Por que existe ─────────────────────────────────────────────────────────
 *
 * O `seed_demo` não cria NENHUMA `BudgetAllocation` — o orçamento entrou no
 * domínio depois dele. Sem esta fixture a matriz vem inteira zerada e nenhum
 * dos testes tem o que asseverar.
 *
 * ─── Por que ORM cru e não `services.budget.criar_alocacao` ─────────────────
 *
 * O service grava uma `BudgetTransaction` a cada criação, e essas são imutáveis
 * por contrato: `save()` de um registro existente levanta ValueError, `delete()`
 * levanta ProtectedError, e `BudgetTransaction.allocation` é PROTECT. Uma
 * alocação criada pelo service, portanto, NÃO PODE SER APAGADA — a fixture
 * vazaria para dentro do banco de demonstração e contaminaria as outras specs.
 *
 * Linhas criadas direto pelo ORM não têm transaction e caem limpo no teardown.
 * `valor_comprometido` e `valor_executado` são colunas materializadas (decisão
 * de projeto documentada em models/budget.py), então gravá-las direto produz
 * exatamente o mesmo estado que o motor de saldo produziria.
 *
 * ─── O território do ADT ────────────────────────────────────────────────────
 *
 * `seed_demo` sorteia o território da Marina (`rnd.choice`), então ele muda a
 * cada re-seed. A fixture o DESCOBRE em tempo de execução e devolve o nome para
 * o teste; fixar um id aqui quebraria no próximo `seed_demo`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/** E-mail do ADT/ACR dos E2E — o mesmo `semPermissao` de helpers/users.ts. */
const EMAIL_ADT =
  process.env.E2E_LEITOR_EMAIL ?? "marina.albuquerque@demo.pdhc.local";

/** Número da Meta que recebe orçamento na fixture. */
export const META_COM_ORCAMENTO = 1;

/** Número da Meta deixada deliberadamente sem nenhuma alocação (teste 7). */
export const META_SEM_ORCAMENTO = 2;

/** Rubrica levada a 85% de comprometido — vermelha em qualquer data (teste 2). */
export const RUBRICA_CRITICA = { slug: "diarias", nome: "Diárias" };

/** Rubrica mantida bem abaixo do limiar, para provar que nem tudo alerta. */
export const RUBRICA_TRANQUILA = {
  slug: "passagens-aereas",
  nome: "Passagens Aéreas",
};

/**
 * Estado usado no drill-down estadual.
 *
 * Fixo, e não descoberto no banco: `seed_demo` cria os sete estados do projeto
 * e PE está entre eles em qualquer re-seed. O que precisa ser descoberto é o
 * TERRITÓRIO da Marina, que é sorteado — ver `territorioAdt`.
 */
export const ESTADO_DRILL = { sigla: "PE", nome: "Pernambuco" };

/** Valor alocado no nível estadual de PE, distinto do nacional de propósito. */
export const ESTADUAL_ALOCADO = "12000.00";

export type OrcamentoFixture = {
  /** Nome do território da Marina, para o teste do recorte do ADT. */
  territorioAdt: string;
  /** Id do mesmo território. */
  territorioAdtId: number;
};

const MARCADOR = "PDHC_E2E_ORCAMENTO";

/**
 * Cria as alocações.
 *
 * Nacional na Meta 1: `diarias` a 85% (85.000 de 100.000) para o vermelho e o
 * banner; `passagens-aereas` a 20% para o verde. Territorial no território da
 * Marina, para que o painel dela tenha o que mostrar — e com valores DIFERENTES
 * dos nacionais, senão o teste do recorte não distinguiria uma coisa da outra.
 *
 * A Meta 2 fica intocada de propósito: é o caso do EmptyState.
 */
const SETUP_SCRIPT = `
import json
from decimal import Decimal

from apps.core.models import State
from apps.core.models.user_profile import UserProfile
from apps.sgp.models import BudgetAllocation, BudgetRubrica, WorkPlanMeta

META_COM = ${META_COM_ORCAMENTO}
META_SEM = ${META_SEM_ORCAMENTO}

meta = WorkPlanMeta.objects.get(numero=META_COM)

# Garante que a Meta do EmptyState esteja mesmo limpa: uma execucao anterior
# interrompida pode ter deixado sobra, e ai o teste 7 falharia sem motivo.
sem = WorkPlanMeta.objects.filter(numero=META_SEM).first()
if sem is not None:
    BudgetAllocation.objects.filter(meta=sem, transactions__isnull=True).delete()

perfil = (
    UserProfile.objects
    .select_related("territorio")
    .filter(user__email="${EMAIL_ADT}", perfil__slug="adt-acr")
    .exclude(territorio__isnull=True)
    .first()
)
if perfil is None:
    raise RuntimeError("ADT dos E2E sem territorio: rode manage.py seed_demo")
territorio = perfil.territorio

diarias = BudgetRubrica.objects.get(slug="${RUBRICA_CRITICA.slug}")
passagens = BudgetRubrica.objects.get(slug="${RUBRICA_TRANQUILA.slug}")

estado_drill = State.objects.get(sigla="${ESTADO_DRILL.sigla}")

def alocar(rubrica, nivel, alocado, comprometido, executado, **escopo):
    # update_or_create e nao create: a unique constraint da combinacao
    # (meta, rubrica, nivel, estado, territorio) recusaria uma segunda execucao,
    # e um run interrompido nao pode travar o proximo.
    BudgetAllocation.objects.update_or_create(
        meta=meta, rubrica=rubrica, nivel=nivel,
        estado=escopo.get("estado"), territorio=escopo.get("territorio"),
        defaults={
            "valor_alocado": Decimal(alocado),
            "valor_comprometido": Decimal(comprometido),
            "valor_executado": Decimal(executado),
        },
    )

# Nacional — o que o UGP/super-admin ve por padrao.
alocar(diarias, "nacional", "100000.00", "85000.00", "10000.00")
alocar(passagens, "nacional", "50000.00", "10000.00", "2500.00")

# Estadual em PE — o alvo do drill-down por estado. Valor DIFERENTE do
# nacional: e o que permite provar que a matriz trocou de nivel, e nao apenas
# filtrou as mesmas linhas.
alocar(passagens, "estadual", "${ESTADUAL_ALOCADO}", "3000.00", "500.00", estado=estado_drill)

# Territorial — o unico nivel que o ADT enxerga. Valores distintos dos
# nacionais: e o que permite provar que ele nao esta vendo o consolidado.
alocar(diarias, "territorial", "7000.00", "1400.00", "700.00", territorio=territorio)

print("${MARCADOR}_SETUP " + json.dumps({
    "territorioAdt": territorio.nome,
    "territorioAdtId": territorio.pk,
}))
`;

/**
 * Remove só o que a fixture criou.
 *
 * O filtro `transactions__isnull=True` é a rede de segurança: se alguém um dia
 * criar orçamento no `seed_demo` pelo service, aquelas linhas terão transactions
 * e este delete passará ao largo delas em vez de estourar ProtectedError.
 */
const TEARDOWN_SCRIPT = `
from apps.sgp.models import BudgetAllocation, WorkPlanMeta

for numero in (${META_COM_ORCAMENTO}, ${META_SEM_ORCAMENTO}):
    meta = WorkPlanMeta.objects.filter(numero=numero).first()
    if meta is not None:
        BudgetAllocation.objects.filter(meta=meta, transactions__isnull=True).delete()

print("${MARCADOR}_TEARDOWN_OK")
`;

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", script],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Cria as alocações e devolve o território do ADT descoberto no banco. */
export function criarOrcamentoFixture(): OrcamentoFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const marca = `${MARCADOR}_SETUP `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) {
    throw new Error(`Falha ao criar a fixture de orçamento:\n${saida}`);
  }
  return JSON.parse(linha.slice(marca.length)) as OrcamentoFixture;
}

/** Apaga as alocações da fixture. */
export function removerOrcamentoFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture de orçamento:\n${saida}`);
  }
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
