import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da montagem e submissão de demanda (Issue #295), no Território RN do
 * ADT Ewerton, montada pelos services do SGD.
 *
 * Verbas territoriais de R$ 10.295,00 (valor-marcador da limpeza) em diárias,
 * passagens, locação e equipamentos. A de diárias tem R$ 10.000 já reservados:
 * sobram R$ 295, e a diária de 2 dias (R$ 600) esbarra na trava territorial.
 *
 * Demandas em Rascunho:
 * - `vazia`: sem solicitações — o teste monta pela tela;
 * - `multipla`: passagem de R$ 6.000 (limite individual de R$ 5.000) e veículo
 *   de R$ 700 (cabe) — uma barrada, a outra não;
 * - `territorial`: a diária de R$ 600 contra os R$ 295 do território;
 * - `equipamento`: kit de R$ 3.000 com 2 cotações — falta 1;
 * - `recusada`: veículo de R$ 1.200 (limite de R$ 1.000) com o pedido de
 *   recurso extra já recusado pela UGP.
 *
 * Os limites do Ewerton são os do seed (R$ 5.000; locação, R$ 1.000). A
 * aprovação de recurso extra eleva o limite e a submissão reserva: o teardown
 * devolve cada limite à foto tirada no setup.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "MONTAR_295_FIXTURE";

export const PREFIXO_295 = "E2E-295";

type Ref = { id: number; titulo: string };

export type MontarDemandaFixture = {
  atividadeId: number;
  municipioNome: string;
  vazia: Ref;
  multipla: Ref & { passagemId: number; veiculoId: number };
  territorial: Ref & { diariaId: number };
  equipamento: Ref;
  recusada: Ref & { veiculoId: number };
  limites: Record<string, { limite: string; comprometido: string; executado: string }>;
};

const COMUM = `
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, BudgetIncreaseRequest
from apps.sgp.models.budget import BudgetAllocation, BudgetRubrica, BudgetTransaction
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.individual_limit import DemandIndividualLimit

P = "${PREFIXO_295}"
VERBA = Decimal("10295.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ids = [str(pk) for pk in demandas.values_list("pk", flat=True)]
    BudgetIncreaseRequest.objects.filter(demanda_id__in=ids).delete()
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    verbas = BudgetAllocation.objects.filter(nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA)
    BudgetTransaction.objects.filter(allocation__in=verbas).delete()
    BudgetTransaction.objects.filter(demanda_id__startswith=P).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    verbas.delete()

def decidir(demanda_id, decisao):
    from apps.sgd.services import recurso_extra as rs
    p = BudgetIncreaseRequest.objects.filter(demanda_id=str(demanda_id)).order_by("-pk").first()
    if p.status == "submetida":
        p = rs.emitir_parecer(p, usuario=articulador, parecer="Parecer da fixture E2E da issue 295.")
    rs.decidir(p, usuario=ugp, decisao=decisao, justificativa="Decisão da fixture E2E da issue 295.")
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from uuid import uuid4
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgp.services import budget as budget_service
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.services import demand as ds, recurso_extra as rs

limpar()
foto = {
    l.rubrica.slug: {"limite": str(l.valor_limite), "comprometido": str(l.valor_comprometido), "executado": str(l.valor_executado)}
    for l in DemandIndividualLimit.objects.filter(solicitante=adt).select_related("rubrica")
}

acao = WorkPlanAcao.objects.order_by("pk").first()
verba = {}
for slug in ("diarias", "passagens-aereas", "locacao-veiculo", "equipamentos-capital"):
    verba[slug] = BudgetAllocation.objects.create(
        meta_id=acao.meta_id, rubrica=BudgetRubrica.objects.get(slug=slug),
        nivel="territorial", territorio_id=territorio_id, valor_alocado=VERBA,
    )
budget_service.reservar(allocation=verba["diarias"], valor=Decimal("10000"), demanda_id=f"{P}-diarias", usuario=ugp)

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Encontro territorial de juventudes", tipo_atividade="intercambio", acao=acao, municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 295.",
)

CPF = "52998224725"
PASSAGEM = {
    "passageiro_nome": "Joana Lima", "passageiro_cpf": CPF, "passageiro_data_nascimento": "1990-05-10",
    "aeroporto_origem": "NAT", "aeroporto_destino": "BSB", "data_hora_ida": "2026-11-20T08:00",
    "ida_e_volta": False, "bagagem_despachada": False, "classe": "economica", "urgencia": "normal",
}
VEICULO = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-20T08:00", "data_hora_devolucao": "2026-11-21T18:00",
    "destino_rota": "Caicó → Mossoró", "estimativa_km": 280, "motorista_incluso": True,
    "combustivel_incluso": True, "numero_passageiros": 12,
}
DIARIA = {
    "beneficiario_nome": "Paulo Rocha", "beneficiario_cpf": CPF, "beneficiario_cargo": "Facilitador",
    "beneficiario_vinculo": "colaborador_externo", "municipio_destino_id": municipio.pk,
    "data_inicio": "2026-11-10", "data_fim": "2026-11-12", "meio_transporte": "rodoviario",
    "justificativa": "Facilitação do encontro.",
}
EQUIPAMENTO = {
    "descricao_equipamento": "Kit de irrigação por gotejamento", "especificacao_tecnica_detalhada": "Kit para 1.000 m².",
    "quantidade": 5, "finalidade_justificativa": "Unidades demonstrativas.", "urgencia": "normal",
}

def demanda(titulo):
    return ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)

def ref(d, **extra):
    return {"id": d.pk, "titulo": d.titulo, **extra}

vazia = demanda("Diárias do facilitador")

multipla = demanda("Caravana com passagem acima do limite")
passagem = ds.adicionar_solicitacao(multipla, tipo="passagem", campos_json=PASSAGEM, valor_estimado=Decimal("6000"))
veiculo = ds.adicionar_solicitacao(multipla, tipo="veiculo", campos_json=VEICULO, valor_estimado=Decimal("700"))

territorial = demanda("Diárias com verba esgotada")
diaria = ds.adicionar_solicitacao(territorial, tipo="diaria", campos_json=DIARIA)

equipamento = demanda("Compra de kits de irrigação")
ds.adicionar_solicitacao(equipamento, tipo="equipamento", campos_json=EQUIPAMENTO, valor_estimado=Decimal("3000"))
for fornecedor in ("Agro Norte", "Irriga Sul"):
    DemandDocument.objects.create(
        demanda=equipamento, tipo="cotacao", fornecedor=fornecedor, nome_original=f"cotacao-{fornecedor}.pdf",
        arquivo_key=f"demandas/{equipamento.pk}/documentos/{uuid4()}.pdf",
        arquivo_url="", content_type="application/pdf", tamanho_bytes=1024, enviado_por=adt,
    )

recusada = demanda("Van recusada")
veiculo_recusado = ds.adicionar_solicitacao(recusada, tipo="veiculo", campos_json=VEICULO, valor_estimado=Decimal("1200"))
rs.criar(
    demanda=recusada, rubrica=BudgetRubrica.objects.get(slug="locacao-veiculo"), usuario=adt,
    justificativa="Recurso extra para a van.",
)
decidir(recusada.pk, "recusar")

print("${MARCADOR}_SETUP " + json.dumps({
    "atividadeId": atividade.pk,
    "municipioNome": municipio.nome,
    "vazia": ref(vazia),
    "multipla": ref(multipla, passagemId=passagem.pk, veiculoId=veiculo.pk),
    "territorial": ref(territorial, diariaId=diaria.pk),
    "equipamento": ref(equipamento),
    "recusada": ref(recusada, veiculoId=veiculo_recusado.pk),
    "limites": foto,
}))
`;

function teardownScript(limites: MontarDemandaFixture["limites"]): string {
  return `${COMUM}
import json
limpar()
foto = json.loads(${JSON.stringify(JSON.stringify(limites))})
for limite in DemandIndividualLimit.objects.filter(solicitante=adt).select_related("rubrica"):
    antes = foto.get(limite.rubrica.slug)
    if antes is None:
        limite.delete()
        continue
    limite.valor_limite = Decimal(antes["limite"])
    limite.valor_comprometido = Decimal(antes["comprometido"])
    limite.valor_executado = Decimal(antes["executado"])
    limite.save(update_fields=["valor_limite", "valor_comprometido", "valor_executado"])
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

function confirmar(saida: string, linha: string): void {
  if (!saida.includes(linha)) throw new Error(`Fixture da #295 não confirmou ${linha}:\n${saida}`);
}

export function criarMontarDemandaFixture(): MontarDemandaFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #295 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as MontarDemandaFixture;
}

export function removerMontarDemandaFixture(fx: MontarDemandaFixture): void {
  confirmar(djangoShellComoDono(teardownScript(fx.limites)), `${MARCADOR}_TEARDOWN_OK`);
}

/** Parecer do Articulador e decisão da UGP no pedido de recurso extra mais recente da demanda. */
export function decidirRecursoExtra(demandaId: number, decisao: "aprovar" | "recusar"): void {
  confirmar(
    djangoShellComoDono(`${COMUM}
decidir(${demandaId}, "${decisao}")
print("${MARCADOR}_DECIDIDO")
`),
    `${MARCADOR}_DECIDIDO`,
  );
}
