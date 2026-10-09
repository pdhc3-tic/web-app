import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da integração Arlo (Issue #298).
 *
 * Importar um pagamento muda a demanda de Autorizada para Em atendimento ou
 * Concluída, e não há caminho de volta pela API. Por isso cada execução monta
 * as próprias demandas Autorizadas pelos services do SGD (criar, solicitar,
 * submeter com reserva das duas travas, pré-autorizar e autorizar) e, no fim,
 * apaga tudo o que criou: demandas, reservas, riscos de glosa e as operações do
 * Arlo registradas durante a execução.
 *
 * - `paga`: uma solicitação de R$ 1.200, paga pelo valor autorizado;
 * - `glosa`: uma solicitação de R$ 1.000, paga com R$ 1.500 (risco de glosa).
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ARLO_FIXTURE";

export const PREFIXO_298 = "E2E-298";

type Ref = { id: number; titulo: string; solicitacaoId: number };

export type ArloFixture = { paga: Ref; glosa: Ref; ultimaOperacao: number };

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, GlosaRisk
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.arlo_import import ArloImport
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit

P = "${PREFIXO_298}"
POOL = Decimal("20298.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
rubrica = BudgetRubrica.objects.get(slug="locacao-veiculo")

def limpar(desde=None):
    demandas = Demand.objects.filter(titulo__startswith=P)
    GlosaRisk.objects.filter(demanda_id__in=[str(pk) for pk in demandas.values_list("pk", flat=True)]).delete()
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    pools = BudgetAllocation.objects.filter(
        nivel="territorial", territorio_id=territorio_id, rubrica=rubrica, valor_alocado=POOL,
    )
    BudgetTransaction.objects.filter(allocation__in=pools).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    DemandIndividualLimit.objects.filter(solicitante=adt, rubrica=rubrica).delete()
    pools.delete()
    ArloImport.objects.filter(nome_original__startswith=P).delete()
    if desde is not None:
        ArloImport.objects.filter(pk__gt=desde).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.db.models import Max
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds, approval as ap

limpar()
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")

acao = WorkPlanAcao.objects.order_by("pk").first()
BudgetAllocation.objects.create(
    meta_id=acao.meta_id, rubrica=rubrica, nivel="territorial", territorio_id=territorio_id, valor_alocado=POOL,
)
DemandIndividualLimit.objects.create(solicitante=adt, rubrica=rubrica, valor_limite=Decimal("10000"))

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Feira territorial", tipo_atividade="intercambio", acao=acao, municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 298.",
)
CAMPOS = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-10T08:00",
    "data_hora_devolucao": "2026-11-11T18:00", "destino_rota": "Caicó → Mossoró",
    "estimativa_km": 280, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 12,
}

def autorizada(titulo, valor):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
    s = ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=CAMPOS, valor_estimado=Decimal(valor))
    ds.submeter_demanda(d, usuario=adt)
    ap.pre_autorizar(d, responsavel=articulador)
    ap.autorizar(d, responsavel=ugp)
    return {"id": d.pk, "titulo": d.titulo, "solicitacaoId": s.pk}

paga = autorizada("Van da feira", "1200")
glosa = autorizada("Van do mutirão", "1000")
ultima = ArloImport.objects.aggregate(m=Max("pk"))["m"] or 0
print("${MARCADOR}_SETUP " + json.dumps({"paga": paga, "glosa": glosa, "ultimaOperacao": ultima}))
`;

const teardownScript = (desde: number) => `${COMUM}
limpar(desde=${Number(desde)})
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

export function criarArloFixture(): ArloFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture do Arlo não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as ArloFixture;
}

export function removerArloFixture(ultimaOperacao: number): void {
  djangoShellComoDono(teardownScript(ultimaOperacao));
}

/** Planilha de retorno no layout padrão do mapeamento de importação. */
export function planilhaDeRetorno(
  linhas: { demanda: number; solicitacao?: number; valorPago: string; processo?: string }[],
): Buffer {
  const cabecalho = "ID Demanda;ID Solicitação;Número do Processo;Data do Pagamento;Valor Pago;Comprovante";
  const corpo = linhas.map((l) =>
    [l.demanda, l.solicitacao ?? "", l.processo ?? `PROC-${l.demanda}`, "15/10/2026", l.valorPago, ""].join(";"),
  );
  return Buffer.from([cabecalho, ...corpo].join("\n"), "utf8");
}
