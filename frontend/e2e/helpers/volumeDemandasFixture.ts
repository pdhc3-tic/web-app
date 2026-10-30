import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Volume alto de demandas para a #323 (NFR de 10.000 registros): uma atividade
 * própria e 10.000 demandas em Rascunho do Ewerton (ADT do Território RN),
 * criadas em lote direto no banco. Em Rascunho, não entram em nenhuma fila de
 * decisão nem reservam saldo; a UGP enxerga todas na visão "Todas".
 *
 * `limpar()` roda no setup (sobras de uma execução interrompida) e no teardown.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "VOLUME_323_FIXTURE";
export const PREFIXO_323 = "E2E-323";
export const VOLUME_DEMANDAS = 10_000;

const COMUM = `
from django.contrib.auth import get_user_model
from apps.sgp.models import Activity
from apps.sgd.models.demand import Demand

P = "${PREFIXO_323}"
U = get_user_model()
adt = U.objects.get(email="ewerton.bandeira@demo.pdhc.local")

def limpar():
    Demand.objects.filter(titulo__startswith=P).delete()
    Activity.objects.filter(titulo__startswith=P).delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao

limpar()
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
quando = timezone.now() + timedelta(days=30)
atividade = Activity.objects.create(
    titulo=f"{P} Atividade com volume alto de demandas", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(),
    municipio=Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first(),
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 323.",
)
Demand.objects.bulk_create(
    [
        Demand(titulo=f"{P} Demanda sintética {i:05d}", activity=atividade, solicitante=adt, status="rascunho")
        for i in range(1, ${VOLUME_DEMANDAS} + 1)
    ],
    batch_size=2000,
)
print("${MARCADOR}_SETUP " + json.dumps({
    "atividadeId": atividade.pk,
    "criadas": Demand.objects.filter(titulo__startswith=P).count(),
}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

export type VolumeDemandasFixture = { atividadeId: number; criadas: number };

/** Como `postgres`, o mesmo das outras fixtures do SGD (row-level security). */
function djangoShell(script: string): string {
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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 300_000 },
  );
}

export function criarVolumeDemandasFixture(): VolumeDemandasFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #323 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as VolumeDemandasFixture;
}

export function removerVolumeDemandasFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #323 não confirmou o teardown:\n${saida}`);
  }
}
