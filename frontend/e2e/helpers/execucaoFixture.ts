import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do painel de execução (Issue #297), com movimentação conhecida no
 * Território RN (o do ADT Ewerton):
 *
 * - três verbas territoriais de R$ 10.297,00 (valor-marcador da limpeza):
 *   - Diárias: R$ 9.782,15 reservados → 95,0%, vermelho;
 *   - Passagens Aéreas: R$ 7.722,75 reservados → 75,0%, amarelo;
 *   - Locação de Veículo: a demanda da fixture (R$ 800, autorizada) e uma
 *     reserva de R$ 2.000 já executada → 7,8%, verde; executado R$ 2.000,
 *     disponível R$ 7.497,00, solicitado e autorizado R$ 800.
 *
 * A demanda passa pelos services do SGD (submeter reserva as duas travas,
 * pré-autorizar, autorizar). As outras reservas usam `budget_service`
 * direto, com `demanda_id` próprio da fixture.
 *
 * O limite individual do Ewerton é compartilhado com o teste manual: a limpeza
 * devolve a ele o que as demandas da fixture reservam, e o teardown repõe o
 * valor do limite (a fixture o aumenta se faltar espaço), em vez de apagá-lo.
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
  /** Foto do limite individual do Ewerton antes da fixture (null = não havia). */
  limiteOriginal: { limite: string; comprometido: string; executado: string } | null;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_297}"
VERBA = Decimal("10297.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
perfil_adt = adt.profiles.select_related("territorio").get(perfil__slug="adt-acr")
territorio_id = perfil_adt.territorio_id

def limpar():
    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from apps.sgd.models.demand_request import DemandRequest
    from apps.sgd.models.individual_limit import DemandIndividualLimit

    demandas = Demand.objects.filter(titulo__startswith=P)
    # Devolve ao limite individual o que as demandas da fixture ainda reservam:
    # apagar a demanda não desfaz a reserva, e o limite é o do teste manual.
    reservado = DemandRequest.objects.filter(
        demanda__in=demandas.filter(status__in=["submetida", "pre_autorizada", "autorizada", "em_atendimento"]),
    ).aggregate(t=Sum(Coalesce("valor_autorizado", "valor_estimado")))["t"] or Decimal("0")
    limite = DemandIndividualLimit.objects.filter(
        solicitante=adt, rubrica=BudgetRubrica.objects.get(slug="locacao-veiculo"),
    ).first()
    if limite is not None and reservado:
        limite.valor_comprometido = max(Decimal("0"), limite.valor_comprometido - reservado)
        limite.save(update_fields=["valor_comprometido"])

    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    verbas = BudgetAllocation.objects.filter(
        nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA,
    )
    BudgetTransaction.objects.filter(allocation__in=verbas).delete()
    BudgetTransaction.objects.filter(demanda_id__startswith=P).delete()
    BudgetTransaction.objects.filter(demanda_id__in=[str(pk) for pk in demandas.values_list("pk", flat=True)]).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    verbas.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgp.services import budget as budget_service
from apps.sgd.models.individual_limit import DemandIndividualLimit
from apps.sgd.services import demand as ds, approval as ap

limpar()
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")
locacao = BudgetRubrica.objects.get(slug="locacao-veiculo")

limite = DemandIndividualLimit.objects.filter(solicitante=adt, rubrica=locacao).first()
foto = None if limite is None else {
    "limite": str(limite.valor_limite),
    "comprometido": str(limite.valor_comprometido),
    "executado": str(limite.valor_executado),
}
if limite is None:
    limite = DemandIndividualLimit.objects.create(solicitante=adt, rubrica=locacao, valor_limite=Decimal("1000"))
if limite.valor_limite - limite.valor_comprometido - limite.valor_executado < Decimal("800"):
    limite.valor_limite = limite.valor_comprometido + limite.valor_executado + Decimal("800")
    limite.save(update_fields=["valor_limite"])

acao = WorkPlanAcao.objects.order_by("pk").first()
verba = {}
for slug in ("diarias", "passagens-aereas", "locacao-veiculo"):
    verba[slug] = BudgetAllocation.objects.create(
        meta_id=acao.meta_id, rubrica=BudgetRubrica.objects.get(slug=slug),
        nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA,
    )

budget_service.reservar(allocation=verba["diarias"], valor=Decimal("9782.15"), demanda_id=f"{P}-diarias", usuario=ugp)
budget_service.reservar(allocation=verba["passagens-aereas"], valor=Decimal("7722.75"), demanda_id=f"{P}-passagens", usuario=ugp)
budget_service.reservar(allocation=verba["locacao-veiculo"], valor=Decimal("2000"), demanda_id=f"{P}-locacao-paga", usuario=ugp)
budget_service.executar(demanda_id=f"{P}-locacao-paga", usuario=ugp)

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
ap.pre_autorizar(d, responsavel=articulador)
ap.autorizar(d, responsavel=ugp)

print("${MARCADOR}_SETUP " + json.dumps({
    "territorioId": territorio_id,
    "territorioNome": perfil_adt.territorio.nome,
    "atividade": {"id": atividade.pk, "titulo": atividade.titulo},
    "acaoId": acao.pk,
    "demanda": {"id": d.pk, "titulo": d.titulo},
    "limiteOriginal": foto,
}))
`;

function teardownScript(foto: ExecucaoFixture["limiteOriginal"]): string {
  return `${COMUM}
import json
from apps.sgd.models.individual_limit import DemandIndividualLimit

limpar()
foto = json.loads(${JSON.stringify(JSON.stringify(foto))})
limite = DemandIndividualLimit.objects.filter(
    solicitante=adt, rubrica=BudgetRubrica.objects.get(slug="locacao-veiculo"),
).first()
if foto is None:
    if limite is not None:
        limite.delete()
elif limite is not None:
    limite.valor_limite = Decimal(foto["limite"])
    limite.save(update_fields=["valor_limite"])
print("${MARCADOR}_TEARDOWN_OK")
`;
}

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

export function removerExecucaoFixture(fx: ExecucaoFixture): void {
  djangoShellComoDono(teardownScript(fx.limiteOriginal));
}
