import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da dotação nacional (#438). Esta suíte GRAVA pela tela a cadeia
 * inteira do orçamento numa rubrica sem nenhum pool:
 *
 *   UGP lança a dotação nacional → UGP distribui ao RN →
 *   Articulador do RN repassa ao Território RN → o ADT do território vê o saldo
 *   no formulário de solicitação do SGD.
 *
 * A rubrica é Equipamentos/Capital: as fixtures que a usam (montar demanda,
 * painel) só criam pools territoriais e os removem no teardown, então ela
 * começa sem pool nacional. O setup confere isso, porque sem essa condição o
 * botão da tela seria "Ajustar" e o POST nacional ficaria sem teste.
 *
 * O setup também cria uma atividade e uma demanda em Rascunho do ADT, de onde o
 * último passo abre o formulário. O teardown restaura a fotografia do orçamento
 * (`orcamentoE2E.ts`), o que apaga os pools e o ledger que a tela gravou, e
 * depois a demanda e a atividade. Roda como `postgres` por causa do RLS.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PDHC_E2E_DOTACAO";
const PREFIXO = "E2E-438";

export const RUBRICA = { slug: "equipamentos-capital", nome: "Equipamentos/Capital" };
/** O tipo de solicitação do SGD que consome a rubrica. */
export const TIPO_SOLICITACAO = "Aquisição de Equipamentos";
/** O estado e o território do ADT Ewerton; o Articulador Hélio atende o RN. */
export const ESTADO = { sigla: "RN" };
export const TERRITORIO = { nome: "Território RN" };

export type DotacaoFixture = { demandaId: number };

const COMUM = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgp.budget.models import BudgetPool, BudgetRubrica
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO}"
FOTO = "dotacao"
rubrica = BudgetRubrica.objects.get(slug="${RUBRICA.slug}")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    restaurar(FOTO)
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds

limpar()
existentes = list(BudgetPool.objects.filter(rubrica=rubrica).values_list("nivel", "estado_id", "territorio_id"))
if existentes:
    raise RuntimeError(f"A rubrica ${RUBRICA.slug} precisa comecar sem pools; encontrados: {existentes}")
fotografar(FOTO)
definir_limite(adt, rubrica, "5000")

territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Oficina de irrigação", tipo_atividade="intercambio", acao=WorkPlanAcao.objects.order_by("pk").first(),
    municipio=municipio, forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 438.",
)
demanda = ds.criar_demanda(titulo=f"{P} Kits de irrigação", activity=atividade, justificativa="", solicitante=adt)
print("${MARCADOR}_SETUP " + json.dumps({"demandaId": demanda.pk}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
}

export function criarDotacaoFixture(): DotacaoFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Falha ao montar a fixture da dotação:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as DotacaoFixture;
}

export function removerDotacaoFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture da dotação:\n${saida}`);
  }
}

/** O `valor_alocado` do pool nacional da rubrica, ou null se não existe. */
export function dotacaoNoBanco(): string | null {
  const saida = djangoShell(`${COMUM}
p = BudgetPool.objects.filter(rubrica=rubrica, nivel="nacional").first()
print("${MARCADOR}_VALOR " + (str(p.valor_alocado) if p else "NENHUMA"))
`);
  const marca = `${MARCADOR}_VALOR `;
  const linha = saida.split("\n").find((l) => l.startsWith(marca));
  if (!linha) throw new Error(`Falha ao ler a dotação:\n${saida}`);
  const valor = linha.slice(marca.length).trim();
  return valor === "NENHUMA" ? null : valor;
}
