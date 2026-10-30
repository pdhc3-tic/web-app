import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Uma atividade atrasada garantida para o A1 da #302: agendada, com o fim dez
 * dias no passado (`filtro_atrasada`: fim já passou e status não terminal).
 * Assim o card "Atividades atrasadas" tem o que contar sem depender de datas
 * do seed. `limpar()` roda no setup e no teardown.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ATRASADA_302_FIXTURE";
const PREFIXO = "E2E-302";

const COMUM = `
from apps.sgp.models import Activity

def limpar():
    Activity.all_objects.filter(titulo__startswith="${PREFIXO}").delete()
`;

const SETUP_SCRIPT = `${COMUM}
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao

limpar()
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
passado = timezone.now() - timedelta(days=10)
atividade = Activity.objects.create(
    titulo="${PREFIXO} Oficina que passou do prazo", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(),
    municipio=Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first(),
    forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=passado, data_fim=passado, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 302.",
)
print("${MARCADOR}_SETUP", atividade.pk)
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

/** Como `postgres`, o mesmo das fixtures do SGD (row-level security). */
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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
}

export function criarAtividadeAtrasada(): number {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #302 não confirmou o setup:\n${saida}`);
  return Number(linha.trim().split(" ")[1]);
}

export function removerAtividadeAtrasada(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #302 não confirmou o teardown:\n${saida}`);
  }
}
