import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da montagem e submissão de demanda (Issue #295), no Território RN do
 * ADT Ewerton, montada pelos services do SGD.
 *
 * Pools territoriais de RN em R$ 10.295,00 em diárias,
 * passagens, locação e equipamentos. A de diárias tem R$ 10.000 já reservados:
 * sobram R$ 295, e a diária de 10 a 12/11 (R$ 750 pela tabela da #358) esbarra na trava territorial.
 *
 * Demandas em Rascunho:
 * - `vazia`: sem solicitações — o teste monta pela tela;
 * - `multipla`: passagem de R$ 6.000 (limite individual de R$ 5.000) e veículo
 *   de R$ 700 (cabe) — uma barrada, a outra não;
 * - `territorial`: a diária (valor calculado pelo backend) contra os R$ 295 do território;
 * - `equipamento`: kit de R$ 3.000 com 2 cotações — falta 1;
 * - `equipamentoCompleto`: kit de R$ 1.000 com 3 cotações válidas;
 * - `recusada`: veículo de R$ 1.200 (limite de R$ 1.000) com o pedido de
 *   recurso extra já recusado pela UGP.
 *
 * Os limites do Ewerton ficam nos valores do seed (R$ 5.000; locação,
 * R$ 1.000), sem nada usado no período. A aprovação de recurso extra eleva o
 * limite e a submissão reserva: o orçamento é fotografado no setup e
 * restaurado no teardown (`orcamentoE2E.ts`, #399).
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "MONTAR_295_FIXTURE";

export const PREFIXO_295 = "E2E-295";

type Ref = { id: number; titulo: string };

export type MontarDemandaFixture = {
  atividadeId: number;
  municipioId: number;
  municipioNome: string;
  vazia: Ref;
  multipla: Ref & { passagemId: number; veiculoId: number };
  /** `diariaValor`: o que o backend calculou para a diária (#358), em texto decimal. */
  territorial: Ref & { diariaId: number; diariaValor: string };
  equipamento: Ref;
  equipamentoCompleto: Ref;
  recusada: Ref & { veiculoId: number };
};

const COMUM = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity, BudgetIncreaseRequest
from apps.sgp.budget.models import BudgetRubrica
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_295}"
FOTO = "montar-demanda"
VERBA = Decimal("10295.00")
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ids = [str(pk) for pk in demandas.values_list("pk", flat=True)]
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    # Antes de apagar: o ledger referencia a atividade e o pedido.
    restaurar(FOTO)
    BudgetIncreaseRequest.objects.filter(demanda_id__in=ids).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()

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
from apps.sgd.models.demand_document import DemandDocument
from apps.sgd.services import demand as ds, recurso_extra as rs

limpar()
fotografar(FOTO)
for slug, valor in (("diarias", "5000"), ("passagens-aereas", "5000"), ("locacao-veiculo", "1000"), ("equipamentos-capital", "5000")):
    definir_limite(adt, BudgetRubrica.objects.get(slug=slug), valor)

acao = WorkPlanAcao.objects.order_by("pk").first()
for slug, comprometido in (("diarias", "10000"), ("passagens-aereas", "0"), ("locacao-veiculo", "0"), ("equipamentos-capital", "0")):
    definir_pool(
        BudgetRubrica.objects.get(slug=slug), "territorial", VERBA, territorio_id=territorio_id, comprometido=comprometido,
    )

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
equipamento_completo = demanda("Compra de bombas d'água")
ds.adicionar_solicitacao(equipamento_completo, tipo="equipamento", campos_json=EQUIPAMENTO, valor_estimado=Decimal("1000"))
for dona, fornecedores in (
    (equipamento, ("Agro Norte", "Irriga Sul")),
    (equipamento_completo, ("Agro Norte", "Irriga Sul", "Campo Verde")),
):
    for fornecedor in fornecedores:
        DemandDocument.objects.create(
            demanda=dona, tipo="cotacao", fornecedor=fornecedor, nome_original=f"cotacao-{fornecedor}.pdf",
            arquivo_key=f"demandas/{dona.pk}/documentos/{uuid4()}.pdf",
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
    "municipioId": municipio.pk,
    "municipioNome": municipio.nome,
    "vazia": ref(vazia),
    "multipla": ref(multipla, passagemId=passagem.pk, veiculoId=veiculo.pk),
    "territorial": ref(territorial, diariaId=diaria.pk, diariaValor=str(diaria.valor_estimado)),
    "equipamento": ref(equipamento),
    "equipamentoCompleto": ref(equipamento_completo),
    "recusada": ref(recusada, veiculoId=veiculo_recusado.pk),
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

/** O argumento ficou por compatibilidade: a restauração vem da fotografia do container. */
export function removerMontarDemandaFixture(_fx?: MontarDemandaFixture): void {
  confirmar(djangoShellComoDono(TEARDOWN_SCRIPT), `${MARCADOR}_TEARDOWN_OK`);
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
