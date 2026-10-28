import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da Fila de Remanejamentos (Issue #321).
 *
 * Monta tudo pelos PRÓPRIOS services do SGD: demandas em Rascunho bloqueadas
 * pelo limite individual (R$ 1.200 pedidos, R$ 1.000 de limite — faltam
 * R$ 200), o pedido de recurso extra de cada uma (`recurso_extra.criar`, que já
 * submete) e o parecer do Articulador onde o teste parte de Com parecer:
 *
 * - `parecer` e `devolver`: Submetidos (fila do Articulador de RN);
 * - `recusar` e `aprovar`: Com parecer (fila da UGP).
 *
 * `aprovar` é criado por último de propósito: é o pedido mais recente do
 * solicitante, e o teste confere que a demanda de `recusar` não mostra o aviso
 * dele — o `GET /sgd/remanejamentos/?demanda=` traz só os pedidos da demanda.
 *
 * O pool territorial de R$ 20.321 cobre as demandas: a aprovação não precisa de
 * alocação de origem.
 *
 * Solicitante: o ADT do Território RN. Articulador de RN: o `articuladorPB`.
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "REMANEJAMENTOS_FIXTURE";

export const PREFIXO_321 = "E2E-321";

type Ref = { pedidoId: number; demandaId: number; titulo: string };

export type RemanejamentosFixture = {
  parecer: Ref;
  devolver: Ref;
  recusar: Ref;
  aprovar: Ref;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, BudgetIncreaseRequest
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.demand import Demand
from apps.sgd.models.individual_limit import DemandIndividualLimit

P = "${PREFIXO_321}"
POOL = Decimal("20321.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
rubrica = BudgetRubrica.objects.get(slug="locacao-veiculo")

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    BudgetIncreaseRequest.objects.filter(demanda_id__in=[str(pk) for pk in demandas.values_list("pk", flat=True)]).delete()
    pools = BudgetAllocation.objects.filter(
        nivel="territorial", territorio_id=territorio_id, rubrica=rubrica, valor_alocado=POOL,
    )
    BudgetTransaction.objects.filter(allocation__in=pools).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    DemandIndividualLimit.objects.filter(solicitante=adt, rubrica=rubrica).delete()
    pools.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds, recurso_extra as rs

limpar()
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")

# A Meta vem da primeira Ação do PT, não de um id fixo: ids mudam a cada reseed.
acao = WorkPlanAcao.objects.order_by("pk").first()
BudgetAllocation.objects.create(
    meta_id=acao.meta_id, rubrica=rubrica, nivel="territorial", territorio_id=territorio_id, valor_alocado=POOL,
)
DemandIndividualLimit.objects.create(solicitante=adt, rubrica=rubrica, valor_limite=Decimal("1000"))

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Caravana agroecológica", tipo_atividade="intercambio", acao=acao, municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 321.",
)
CAMPOS = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-20T08:00",
    "data_hora_devolucao": "2026-11-21T18:00", "destino_rota": "Natal → Mossoró",
    "estimativa_km": 300, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 14,
}

def pedido(titulo, com_parecer=False):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
    ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=CAMPOS, valor_estimado=Decimal("1200"))
    p = rs.criar(demanda=d, rubrica=rubrica, usuario=adt, justificativa=f"Recurso extra para {titulo.lower()}.")
    if com_parecer:
        p = rs.emitir_parecer(p, usuario=articulador, parecer="Favorável: a caravana é prioridade do território.")
    return {"pedidoId": p.pk, "demandaId": d.pk, "titulo": d.titulo}

saida = {
    "parecer": pedido("Van para a caravana"),
    "devolver": pedido("Van sem roteiro definido"),
    "recusar": pedido("Van em duplicidade", com_parecer=True),
    "aprovar": pedido("Van da comitiva", com_parecer=True),
}
print("${MARCADOR}_SETUP " + json.dumps(saida))
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

export function criarRemanejamentosFixture(): RemanejamentosFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) {
    throw new Error(`Fixture da Fila de Remanejamentos não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as RemanejamentosFixture;
}

export function removerRemanejamentosFixture(): void {
  djangoShellComoDono(TEARDOWN_SCRIPT);
}
