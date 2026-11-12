import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture do ciclo de vida completo da demanda (Issue #317).
 *
 * Diferente das fixtures das #295 e #296, ela NÃO cria demanda nenhuma: as
 * jornadas criam, montam, submetem e decidem tudo pela tela. Aqui só fica o
 * que o `seed_demo` não entrega pronto para isso:
 *
 * - uma atividade agendada por jornada, no Território RN do ADT Ewerton;
 * - uma atividade com uma demanda em Rascunho, só para consultar o saldo na
 *   montagem (a jornada do cancelamento compara o antes e o depois);
 * - o pool territorial de alimentação do RN em R$ 10.317,00, sem nada
 *   comprometido nem executado (#399: o pool é único por rubrica e local, então
 *   a fixture ajusta o do seed em vez de criar outro);
 * - o limite individual de alimentação do Ewerton em R$ 5.000 no período, sem
 *   nada usado.
 *
 * O orçamento é fotografado no setup e restaurado no teardown
 * (`orcamentoE2E.ts`).
 *
 * O setup também limpa o que uma execução interrompida tenha deixado: os
 * testes não dependem de estado anterior.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "CICLO_317_FIXTURE";

export const PREFIXO_317 = "E2E-317";

type Ref = { id: number; titulo: string };

export type CicloDemandaFixture = {
  feliz: Ref;
  devolucao: Ref;
  recusa: Ref;
  cancelamento: Ref;
  /** Demanda em Rascunho onde a jornada do cancelamento lê o saldo. */
  consultaSaldo: Ref;
};

const COMUM = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, BudgetIncreaseRequest
from apps.sgp.budget.models import BudgetRubrica
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_317}"
FOTO = "ciclo-demanda"
VERBA = Decimal("10317.00")
RUBRICA = "alimentacao-refeicoes"
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ids = [str(pk) for pk in demandas.values_list("pk", flat=True)]
    BudgetIncreaseRequest.objects.filter(demanda_id__in=ids).delete()
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    # Antes de apagar: o ledger referencia a atividade.
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
fotografar(FOTO)
rubrica = BudgetRubrica.objects.get(slug=RUBRICA)
acao = WorkPlanAcao.objects.order_by("pk").first()
definir_pool(rubrica, "territorial", VERBA, territorio_id=territorio_id)
definir_limite(adt, rubrica, "5000")

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)

def atividade(titulo):
    a = Activity.objects.create(
        titulo=f"{P} {titulo}", tipo_atividade="intercambio", acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
        data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
        descricao_narrativa="Criada pela fixture E2E da issue 317.",
    )
    return {"id": a.pk, "titulo": a.titulo}

saldo = atividade("Reunião do colegiado territorial")
consulta = ds.criar_demanda(
    titulo=f"{P} Consulta de saldo", activity=Activity.objects.get(pk=saldo["id"]), justificativa="", solicitante=adt,
)

print("${MARCADOR}_SETUP " + json.dumps({
    "feliz": atividade("Feira agroecológica do território"),
    "devolucao": atividade("Oficina de beneficiamento de frutas"),
    "recusa": atividade("Encontro de mulheres rurais"),
    "cancelamento": atividade("Dia de campo em quintais produtivos"),
    "consultaSaldo": {"id": consulta.pk, "titulo": consulta.titulo},
}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

function djangoShellComoDono(script: string): string {
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

export function criarCicloDemandaFixture(): CicloDemandaFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #317 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as CicloDemandaFixture;
}

/** O argumento ficou por compatibilidade: a restauração vem da fotografia do container. */
export function removerCicloDemandaFixture(_fx?: CicloDemandaFixture): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #317 não confirmou o teardown:\n${saida}`);
  }
}
