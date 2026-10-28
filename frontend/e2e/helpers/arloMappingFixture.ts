import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do mapeamento Arlo ↔ SGD (Issue #320).
 *
 * A spec cria, edita e reordena colunas de verdade pelo CRUD da BE-9, então o
 * setup tira uma foto do mapeamento e o teardown volta exatamente a ela: apaga
 * as colunas que a spec criou e devolve coluna, formato, ordem e situação das
 * que já existiam. O nome da coluna é único na direção, por isso a volta passa
 * por um nome provisório antes do definitivo.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ARLO_MAPPING_320_FIXTURE";

export type ColunaFoto = {
  id: number;
  direcao: "exportacao" | "importacao";
  campo_sgd: string;
  coluna_arlo: string;
  formato: string;
  ordem: number;
  ativo: boolean;
};

export type ArloMappingFixture = { colunas: ColunaFoto[] };

const SETUP_SCRIPT = `
import json
from apps.sgd.models.arlo_field_mapping import ArloFieldMapping as M

print("${MARCADOR}_SETUP " + json.dumps({"colunas": [
    {"id": m.pk, "direcao": m.direcao, "campo_sgd": m.campo_sgd, "coluna_arlo": m.coluna_arlo,
     "formato": m.formato, "ordem": m.ordem, "ativo": m.ativo}
    for m in M.objects.order_by("direcao", "ordem", "pk")
]}))
`;

function teardownScript(foto: ColunaFoto[]): string {
  return `
import json
from django.db import transaction
from apps.sgd.models.arlo_field_mapping import ArloFieldMapping as M

foto = json.loads(${JSON.stringify(JSON.stringify(foto))})
with transaction.atomic():
    M.objects.exclude(pk__in=[c["id"] for c in foto]).delete()
    for c in foto:
        M.objects.filter(pk=c["id"]).update(coluna_arlo=f"__e2e_{c['id']}")
    for c in foto:
        M.objects.filter(pk=c["id"]).update(
            coluna_arlo=c["coluna_arlo"], formato=c["formato"], ordem=c["ordem"], ativo=c["ativo"],
        )
print("${MARCADOR}_TEARDOWN_OK")
`;
}

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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
}

export function criarArloMappingFixture(): ArloMappingFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #320 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as ArloMappingFixture;
}

export function removerArloMappingFixture(fx: ArloMappingFixture): void {
  const saida = djangoShell(teardownScript(fx.colunas));
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #320 não confirmou o teardown:\n${saida}`);
  }
}
