import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do Painel de Demandas com filtros, exportação e cancelamento pelo
 * solicitante (#456).
 *
 * Em nome do ADT do Território RN (o `adt` de helpers/users.ts), uma atividade
 * Agendada e duas demandas em Rascunho, sem solicitação — nada é reservado no
 * orçamento, então não há saldo a fotografar nem a restaurar:
 *
 * - `aCancelar`: o ADT a cancela pela tela;
 * - `filtrada`: aparece no filtro de status Rascunho e na exportação.
 *
 * Tudo leva o prefixo `E2E-456`, que o teardown usa para limpar. Roda como
 * `postgres` por causa da row-level security de `sgd_demand`.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PAINEL_FILTROS_FIXTURE";
export const PREFIXO_456 = "E2E-456";

type Ref = { id: number; titulo: string };

export type PainelFiltrosFixture = {
  atividadeId: number;
  aCancelar: Ref;
  filtrada: Ref;
};

const COMUM = `
from apps.sgp.models import Activity
from apps.sgd.models.demand import Demand
from apps.sgd.models.approval_step import ApprovalStep

P = "${PREFIXO_456}"

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds

limpar()
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=30)
atividade = Activity.objects.create(
    titulo=f"{P} Oficina de beneficiamento", tipo_atividade="oficina",
    acao=WorkPlanAcao.objects.order_by("pk").first(), municipio=municipio,
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 456.",
)
rascunho = lambda titulo: ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
a = rascunho("Rascunho a cancelar")
f = rascunho("Rascunho para o filtro")
ref = lambda d: {"id": d.pk, "titulo": d.titulo}
print("${MARCADOR}_SETUP " + json.dumps({"atividadeId": atividade.pk, "aCancelar": ref(a), "filtrada": ref(f)}))
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

export function criarPainelFiltrosFixture(): PainelFiltrosFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture do painel com filtros não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as PainelFiltrosFixture;
}

export function removerPainelFiltrosFixture(): void {
  const saida = djangoShellComoDono(`${COMUM}\nlimpar()\nprint("${MARCADOR}_TEARDOWN_OK")`);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) throw new Error(`Falha ao limpar a fixture:\n${saida}`);
}

/** Status da demanda no banco. */
export function statusDaDemanda(id: number): string {
  const saida = djangoShellComoDono(`
from apps.sgd.models.demand import Demand
print("${MARCADOR}_STATUS " + Demand.objects.get(pk=${id}).status)
`);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_STATUS `));
  if (!linha) throw new Error(`Falha ao ler o status:\n${saida}`);
  return linha.slice(`${MARCADOR}_STATUS `.length).trim();
}
