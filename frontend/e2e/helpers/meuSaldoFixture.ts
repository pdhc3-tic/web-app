import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture do "Meu saldo" (#401), no Território RN do ADT Ewerton.
 *
 * - Limite de Locação de Veículos do Ewerton em R$ 1.000, sem nada usado, e o
 *   pool territorial da rubrica em R$ 10.000.
 * - `submeter`: demanda em Rascunho com uma van de R$ 700, que cabe nas duas
 *   travas — o teste a submete pela tela e a reserva aparece no extrato. Com
 *   70% comprometido, a rubrica passa a amarelo.
 * - `rascunho`: outra demanda em Rascunho com uma van de R$ 200, que o atalho
 *   do recurso extra lista.
 *
 * O orçamento é fotografado no setup e restaurado no teardown (`orcamentoE2E.ts`).
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "MEU_SALDO_401_FIXTURE";

export const PREFIXO_401 = "E2E-401";

type Ref = { id: number; titulo: string };

export type MeuSaldoFixture = { submeter: Ref; rascunho: Ref };

const COMUM = `${ORCAMENTO_E2E_PY}
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_401}"
FOTO = "meu-saldo-401"
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    # Antes de apagar: o ledger referencia a atividade.
    restaurar(FOTO)
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgp.budget.models import BudgetRubrica
from apps.sgd.services import demand as ds

limpar()
fotografar(FOTO)
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
veiculo = BudgetRubrica.objects.get(slug="locacao-veiculo")
definir_limite(adt, veiculo, "1000")
definir_pool(veiculo, "territorial", "10000.00", territorio_id=territorio_id)

quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Intercâmbio de sementes", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(),
    municipio=Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first(),
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 401.",
)
VEICULO = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-12-01T08:00", "data_hora_devolucao": "2026-12-02T18:00",
    "destino_rota": "Caicó → Mossoró", "estimativa_km": 280, "motorista_incluso": True,
    "combustivel_incluso": True, "numero_passageiros": 12,
}

def demanda(titulo, valor):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
    ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=VEICULO, valor_estimado=Decimal(valor))
    return {"id": d.pk, "titulo": d.titulo}

print("${MARCADOR}_SETUP " + json.dumps({
    "submeter": demanda("Van do intercâmbio", "700"),
    "rascunho": demanda("Van da volta", "200"),
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

export function criarMeuSaldoFixture(): MeuSaldoFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #401 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as MeuSaldoFixture;
}

export function removerMeuSaldoFixture(): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #401 não confirmou o teardown:\n${saida}`);
  }
}
