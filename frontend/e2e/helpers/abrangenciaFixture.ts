import { execFileSync } from "node:child_process";
import path from "node:path";
import { ORCAMENTO_E2E_PY } from "./orcamentoE2E";

/**
 * Fixture da abrangência territorial da demanda (#361, backend #352).
 *
 * Uma atividade agendada de PE, da ADT Marina, que o ADT Ewerton (Território
 * RN) acha pela busca do formulário e vincula a uma demanda nova — pela tela,
 * desde que a busca saiu do recorte territorial do SGP (#361, PR #422).
 *
 * A solicitação entra por `adicionarSolicitacao361`, depois que a tela cria a
 * demanda: uma locação de veículo de R$ 700, que cabe no limite de R$ 1.000
 * do Ewerton e no pool territorial de RN. Assim a submissão passa e a demanda
 * vai para a fila do Articulador de RN, não para a de PE. O formulário de
 * veículo tem E2E próprio (`montar-demanda`). O orçamento é fotografado no
 * setup e restaurado no teardown.
 *
 * Roda como `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ABRANGENCIA_361_FIXTURE";

export const PREFIXO_361 = "E2E-361";

export type AbrangenciaFixture = {
  atividadeTitulo: string;
  /** Como a tela deve mostrar: "Território (UF)". */
  abrangencia: string;
  estadoDemanda: string;
  estadoAtividade: string;
  /** Como "Analisada por" deve mostrar: os nomes, separados por vírgula. */
  articuladores: string;
};

const COMUM = `${ORCAMENTO_E2E_PY}
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_361}"
FOTO = "abrangencia-361"
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
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgp.budget.models import BudgetRubrica
from apps.sgd.services import contexto

limpar()
fotografar(FOTO)

marina = U.objects.get(email="marina.albuquerque@demo.pdhc.local")
territorio_adt = adt.profiles.get(perfil__slug="adt-acr").territorio
veiculo = BudgetRubrica.objects.get(slug="locacao-veiculo")
definir_limite(adt, veiculo, "1000")
definir_pool(veiculo, "territorial", "10000.00", territorio_id=territorio_adt.pk)

municipio_pe = Municipality.objects.filter(state__sigla="PE").order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Feira agroecológica em PE", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(), municipio=municipio_pe,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=marina,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=marina,
    descricao_narrativa="Criada pela fixture E2E da issue 361.",
)

estado, territorio = contexto.abrangencia_para_nova_demanda(solicitante=adt)
assert estado and estado != "PE" and territorio, (estado, territorio)

print("${MARCADOR}_SETUP " + json.dumps({
    "atividadeTitulo": atividade.titulo,
    "abrangencia": f"{territorio.nome} ({estado})",
    "estadoDemanda": estado,
    "estadoAtividade": "PE",
    "articuladores": ", ".join(a["nome"] for a in contexto.articuladores_do_estado(estado)),
}))
`;

const SOLICITACAO_SCRIPT = (demandaId: number) => `${COMUM}
from decimal import Decimal
from apps.sgd.services import demand as ds

demanda = Demand.objects.get(pk=${demandaId}, titulo__startswith=P, solicitante=adt)
ds.adicionar_solicitacao(demanda, tipo="veiculo", valor_estimado=Decimal("700"), campos_json={
    "tipo_veiculo": "van", "data_hora_retirada": "2026-12-01T08:00", "data_hora_devolucao": "2026-12-02T18:00",
    "destino_rota": "Mossoró → Caruaru", "estimativa_km": 600, "motorista_incluso": True,
    "combustivel_incluso": True, "numero_passageiros": 10,
})
print("${MARCADOR}_SOLICITACAO_OK")
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

export function criarAbrangenciaFixture(): AbrangenciaFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #361 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as AbrangenciaFixture;
}

export function removerAbrangenciaFixture(): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #361 não confirmou o teardown:\n${saida}`);
  }
}

/** Locação de veículo de R$ 700 na demanda que a tela criou. */
export function adicionarSolicitacao361(demandaId: number): void {
  const saida = djangoShellComoDono(SOLICITACAO_SCRIPT(demandaId));
  if (!saida.includes(`${MARCADOR}_SOLICITACAO_OK`)) {
    throw new Error(`Fixture da #361 não adicionou a solicitação:
${saida}`);
  }
}
