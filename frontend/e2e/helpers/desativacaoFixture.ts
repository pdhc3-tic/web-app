import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da desativação de usuário com aviso de impacto (#406).
 *
 * Cria uma técnica ADT descartável no território do Ewerton, técnica de uma
 * atividade própria, com limite individual de Locação de veículo em R$ 2.000 e
 * três demandas, todas pelos services do SGD:
 * - `submetida`: R$ 800, submetida, com a reserva no limite e no pool;
 * - `rascunho`: R$ 300, nunca submetida, sem reserva;
 * - `autorizada`: R$ 500, submetida, pré-autorizada e autorizada.
 *
 * O impacto da desativação é, então, conhecido: cancela a submetida e o
 * rascunho, libera R$ 800 em Locação de veículo, e a autorizada fica.
 *
 * Desativar alguém do seed mudaria os dados das outras specs; por isso a
 * pessoa é criada aqui e apagada no fim. O orçamento é fotografado no setup e
 * restaurado no teardown (`orcamentoE2E.ts`). As notificações que a submissão e
 * o cancelamento mandam ao Articulador levam o prefixo no título e saem também.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "DESATIVACAO_406_FIXTURE";

export const PREFIXO_406 = "E2E-406";
export const EMAIL_406 = "e2e-406.desativar@demo.pdhc.local";
export const NOME_406 = "E2E-406 Técnica a Desativar";

type DemandaRef = { id: number; titulo: string };

export type DesativacaoFixture = {
  userId: number;
  rubrica: { id: number; nome: string };
  demandas: { submetida: DemandaRef; rascunho: DemandaRef; autorizada: DemandaRef };
};

export type EstadoDepois = {
  ativo: boolean;
  status: Record<string, string>;
  limiteComprometido: string;
  poolComprometido: string;
};

const COMUM = `${ORCAMENTO_E2E_PY}
import json
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.core.models.notifications import Notification
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.demand import Demand
from apps.sgp.budget.models import BudgetPool, BudgetRubrica, SpendingLimit
from apps.sgp.models import Activity

P = "${PREFIXO_406}"
EMAIL = "${EMAIL_406}"
FOTO = "desativacao-406"
U = get_user_model()
ewerton = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = ewerton.profiles.get(perfil__slug="adt-acr").territorio_id
locacao = BudgetRubrica.objects.get(slug="locacao-veiculo")

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    # Antes de apagar: o ledger referencia a atividade.
    restaurar(FOTO)
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    Notification.objects.filter(titulo__contains=P).delete()
    pessoa = U.objects.filter(email=EMAIL).first()
    if pessoa is None:
        return
    # A auditoria é imutável por trigger, e apagar a pessoa faria o Django zerar
    # o \`user\` das linhas dela. Saem as linhas que a própria fixture gerou (as
    # da pessoa e as que têm a pessoa como alvo), com o trigger desligado só
    # nesta transação, como o \`restaurar\` faz com o ledger.
    from django.db import connection, transaction
    from apps.core.models import AuditLog
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL session_replication_role = replica")
        trilha = AuditLog.objects.filter(user=pessoa) | AuditLog.objects.filter(entidade="User", entidade_id=str(pessoa.pk))
        trilha._raw_delete(trilha.db)
        pessoa.delete()
`;

const SETUP_SCRIPT = `${COMUM}
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality, Role, UserProfile
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds, workflow as wf

limpar()
fotografar(FOTO)
articulador = U.objects.get(email="helio.fontenele@demo.pdhc.local")
ugp = U.objects.get(email="beatriz.nogueira@demo.pdhc.local")

tecnica = U.objects.create(email=EMAIL, nome="${NOME_406}", ativo=True)
UserProfile.objects.create(user=tecnica, perfil=Role.objects.get(slug="adt-acr"), territorio_id=territorio_id)
definir_limite(tecnica, locacao, "2000")
definir_pool(locacao, "territorial", "50000.00", territorio_id=territorio_id)

municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Intercâmbio de sementes", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(), municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=tecnica,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=tecnica,
    descricao_narrativa="Criada pela fixture E2E da issue 406.",
)

def demanda(titulo, valor):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=tecnica)
    ds.adicionar_solicitacao(d, tipo="veiculo", campos_json={
        "tipo_veiculo": "van", "data_hora_retirada": "2026-12-01T08:00",
        "data_hora_devolucao": "2026-12-02T18:00", "destino_rota": "Caicó → Mossoró",
        "estimativa_km": 280, "motorista_incluso": True, "combustivel_incluso": True,
        "numero_passageiros": 12,
    }, valor_estimado=Decimal(valor))
    return d

submetida = demanda("Van do intercâmbio", "800")
ds.submeter_demanda(submetida, usuario=tecnica)
rascunho = demanda("Van da visita de retorno", "300")
autorizada = demanda("Van da feira", "500")
ds.submeter_demanda(autorizada, usuario=tecnica)
wf.executar_transicao(autorizada, "pre_autorizada", ator=articulador)
wf.executar_transicao(autorizada, "autorizada", ator=ugp)

print("${MARCADOR}_SETUP " + json.dumps({
    "userId": tecnica.pk,
    "rubrica": {"id": locacao.pk, "nome": locacao.nome},
    "demandas": {
        nome: {"id": d.pk, "titulo": d.titulo}
        for nome, d in (("submetida", submetida), ("rascunho", rascunho), ("autorizada", autorizada))
    },
}))
`;

const ESTADO_SCRIPT = `${COMUM}
from apps.sgp.budget import limites
tecnica = U.objects.get(email=EMAIL)
hoje = limites.hoje()
limite = SpendingLimit.objects.get(
    escopo="individual", user=tecnica, rubrica=locacao, periodo_inicio__lte=hoje, periodo_fim__gte=hoje,
)
pool = BudgetPool.objects.get(rubrica=locacao, nivel="territorial", territorio_id=territorio_id)
print("${MARCADOR}_ESTADO " + json.dumps({
    "ativo": tecnica.ativo,
    "status": {str(d.pk): d.status for d in Demand.objects.filter(titulo__startswith=P)},
    "limiteComprometido": str(limite.valor_comprometido),
    "poolComprometido": str(pool.valor_comprometido),
}))
`;

const REATIVAR_SCRIPT = `${COMUM}
U.objects.filter(email=EMAIL).update(ativo=True)
print("${MARCADOR}_REATIVADA")
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

function linhaJson<T>(saida: string, rotulo: string): T {
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_${rotulo} `));
  if (!linha) throw new Error(`Fixture da #406 não devolveu ${rotulo}:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_${rotulo} `.length)) as T;
}

export function criarDesativacaoFixture(): DesativacaoFixture {
  return linhaJson<DesativacaoFixture>(djangoShellComoDono(SETUP_SCRIPT), "SETUP");
}

/** O que ficou no banco: se a pessoa está ativa, o status das demandas e o comprometido. */
export function lerEstadoDepois(): EstadoDepois {
  return linhaJson<EstadoDepois>(djangoShellComoDono(ESTADO_SCRIPT), "ESTADO");
}

/** Volta a pessoa a ativa, sem mexer nas demandas. */
export function reativarPessoa(): void {
  const saida = djangoShellComoDono(REATIVAR_SCRIPT);
  if (!saida.includes(`${MARCADOR}_REATIVADA`)) throw new Error(`Fixture da #406 não reativou:\n${saida}`);
}

export function removerDesativacaoFixture(): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #406 não confirmou o teardown:\n${saida}`);
  }
}
