import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Técnicos de verdade para o `tecnicos.spec` (#237, A2 da #302). O seed não
 * cadastra nenhum técnico, então a fixture cria usuários próprios (e-mail
 * `e2e302.*`) e, para eles:
 *
 * - `ana`: técnica ativa no território do ADT do E2E (`semPermissao`), para
 *   que ele também a enxergue;
 * - `maria`: técnica inativa, sem território nem OSC;
 * - `elegivel`: usuário sem vínculo, para o cadastro pela tela;
 * - `conflito`: uma OSC com área de atuação e um território fora dela — o
 *   par que o backend recusa com `conflito_vinculo`.
 *
 * `limpar()` roda no setup e no teardown e leva também o que a spec criou.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "TECNICOS_302_FIXTURE";

export type TecnicosFixture = {
  ana: { id: number; nome: string; papel: string; territorio: string; osc: string | null };
  maria: { id: number; nome: string; papel: string };
  elegivel: { nome: string };
  conflito: { territorio: string; osc: string };
};

const COMUM = `
from django.contrib.auth import get_user_model
from apps.sgp.models import Tecnico
U = get_user_model()

def limpar():
    Tecnico.objects.filter(user__email__startswith="e2e302.").delete()
    U.objects.filter(email__startswith="e2e302.").delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from apps.core.models import Organization, Territory

limpar()
leitor = U.objects.get(email="marina.albuquerque@demo.pdhc.local")
territorio = leitor.profiles.get(perfil__slug="adt-acr").territorio
osc = (
    Organization.objects.filter(territorios=territorio).order_by("nome").first()
    or Organization.objects.filter(territorios__isnull=True).order_by("nome").first()
)

def usuario(apelido, nome):
    return U.objects.create_user(email=f"e2e302.{apelido}@demo.pdhc.local", nome=nome)

ana = Tecnico.objects.create(
    user=usuario("ana", "E2E-302 Ana Técnica"), papel="ADT", territorio=territorio, osc=osc, ativo=True,
)
maria = Tecnico.objects.create(user=usuario("maria", "E2E-302 Maria Técnica"), papel="Coordenadora", ativo=False)
usuario("elegivel", "E2E-302 Elegível Técnico")

osc_conflito = Organization.objects.filter(territorios__isnull=False).distinct().order_by("nome").first()
territorio_conflito = Territory.objects.filter(ativo=True).exclude(pk__in=osc_conflito.territorios.values("pk")).order_by("nome").first()

print("${MARCADOR}_SETUP " + json.dumps({
    "ana": {"id": ana.pk, "nome": ana.user.nome, "papel": ana.papel, "territorio": territorio.nome, "osc": osc.nome if osc else None},
    "maria": {"id": maria.pk, "nome": maria.user.nome, "papel": maria.papel},
    "elegivel": {"nome": "E2E-302 Elegível Técnico"},
    "conflito": {"territorio": territorio_conflito.nome, "osc": osc_conflito.nome},
}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

/** Como `postgres`, o mesmo das outras fixtures (row-level security). */
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

export function criarTecnicosFixture(): TecnicosFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture de técnicos não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as TecnicosFixture;
}

export function removerTecnicosFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture de técnicos não confirmou o teardown:\n${saida}`);
  }
}
