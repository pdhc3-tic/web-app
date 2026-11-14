import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture do painel de execução (Issue #297), com movimentação conhecida no
 * Território RN (o do ADT Ewerton):
 *
 * - os três pools territoriais de RN em R$ 10.297,00:
 *   - Diárias: R$ 9.782,15 reservados → 95,0%, vermelho;
 *   - Passagens Aéreas: R$ 7.722,75 reservados → 75,0%, amarelo;
 *   - Locação de Veículo: a demanda da fixture (R$ 800, autorizada) e uma
 *     reserva de R$ 2.000 já executada → 7,8%, verde; executado R$ 2.000,
 *     disponível R$ 7.497,00, solicitado e autorizado R$ 800.
 *
 * A demanda passa pelos services do SGD (submeter reserva as duas travas,
 * pré-autorizar, autorizar). O comprometido e o executado das outras rubricas
 * entram direto no pool (#399: o pool materializa os dois valores).
 *
 * O limite individual de locação do Ewerton fica em R$ 1.000 no período. O
 * orçamento é fotografado no setup e restaurado no teardown (`orcamentoE2E.ts`).
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "EXECUCAO_297_FIXTURE";

export const PREFIXO_297 = "E2E-297";

export type ExecucaoFixture = {
  territorioId: number;
  territorioNome: string;
  atividade: { id: number; titulo: string };
  acaoId: number;
  demanda: { id: number; titulo: string };
};

const COMUM = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgp.budget.models import BudgetRubrica
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_297}"
FOTO = "execucao"
VERBA = Decimal("10297.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
perfil_adt = adt.profiles.select_related("territorio").get(perfil__slug="adt-acr")
territorio_id = perfil_adt.territorio_id

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
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds, workflow as wf

limpar()
fotografar(FOTO)
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")
locacao = BudgetRubrica.objects.get(slug="locacao-veiculo")

definir_limite(adt, locacao, "1000")

acao = WorkPlanAcao.objects.order_by("pk").first()
for slug, comprometido, executado in (
    ("diarias", "9782.15", "0"), ("passagens-aereas", "7722.75", "0"), ("locacao-veiculo", "0", "2000"),
):
    definir_pool(
        BudgetRubrica.objects.get(slug=slug), "territorial", VERBA, territorio_id=territorio_id,
        comprometido=comprometido, executado=executado,
    )

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Feira agroecológica regional", tipo_atividade="intercambio", acao=acao, municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 297.",
)
d = ds.criar_demanda(titulo=f"{P} Van da feira agroecológica", activity=atividade, justificativa="", solicitante=adt)
ds.adicionar_solicitacao(d, tipo="veiculo", campos_json={
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-10T08:00",
    "data_hora_devolucao": "2026-11-11T18:00", "destino_rota": "Caicó → Mossoró",
    "estimativa_km": 280, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 12,
}, valor_estimado=Decimal("800"))
ds.submeter_demanda(d, usuario=adt)
wf.executar_transicao(d, "pre_autorizada", ator=articulador)
wf.executar_transicao(d, "autorizada", ator=ugp)

print("${MARCADOR}_SETUP " + json.dumps({
    "territorioId": territorio_id,
    "territorioNome": perfil_adt.territorio.nome,
    "atividade": {"id": atividade.pk, "titulo": atividade.titulo},
    "acaoId": acao.pk,
    "demanda": {"id": d.pk, "titulo": d.titulo},
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

export function criarExecucaoFixture(): ExecucaoFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) {
    throw new Error(`Fixture do painel de execução não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as ExecucaoFixture;
}

/** O argumento ficou por compatibilidade: a restauração vem da fotografia do container. */
export function removerExecucaoFixture(_fx?: ExecucaoFixture): void {
  djangoShellComoDono(TEARDOWN_SCRIPT);
}
