import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da configuração tipo → rubrica (Issue #319).
 *
 * O `seed_demo` deixa um mapeamento ativo por tipo. A spec desativa, cria e
 * edita de verdade pelo CRUD da BE-8, então o setup tira uma foto dos
 * mapeamentos e o teardown volta exatamente a ela: apaga o que a spec criou
 * e devolve rubrica e situação dos que já existiam.
 *
 * Devolve também o catálogo de rubricas com os ids reais, que os testes de
 * criar e trocar a rubrica usam quando `GET /sgp/rubricas/` existir
 * (pendencias-backend-sprint-11.md, item 1).
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "TIPO_RUBRICA_319_FIXTURE";

export type MapeamentoFoto = { id: number; tipo: string; rubrica: number; ativo: boolean };
export type RubricaFixture = { id: number; slug: string; nome: string; ativo: boolean };

export type TipoRubricaFixture = {
  mapeamentos: MapeamentoFoto[];
  rubricas: RubricaFixture[];
};

const SETUP_SCRIPT = `
import json
from apps.sgp.models.budget import BudgetRubrica
from apps.sgd.models.demand_type_rubrica_mapping import DemandTypeRubricaMapping as M

print("${MARCADOR}_SETUP " + json.dumps({
    "mapeamentos": [
        {"id": m.pk, "tipo": m.tipo, "rubrica": m.rubrica_id, "ativo": m.ativo}
        for m in M.objects.order_by("pk")
    ],
    "rubricas": [
        {"id": r.pk, "slug": r.slug, "nome": r.nome, "ativo": r.ativo}
        for r in BudgetRubrica.objects.order_by("nome")
    ],
}))
`;

function teardownScript(foto: MapeamentoFoto[]): string {
  return `
import json
from django.db import transaction
from apps.sgd.models.demand_type_rubrica_mapping import DemandTypeRubricaMapping as M

foto = json.loads(${JSON.stringify(JSON.stringify(foto))})
with transaction.atomic():
    M.objects.exclude(pk__in=[m["id"] for m in foto]).delete()
    # Primeiro todos inativos: a constraint de um ativo por tipo não pode
    # barrar a volta no meio do caminho.
    M.objects.update(ativo=False)
    for m in foto:
        M.objects.filter(pk=m["id"]).update(rubrica_id=m["rubrica"], ativo=m["ativo"])
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

export function criarTipoRubricaFixture(): TipoRubricaFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #319 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as TipoRubricaFixture;
}

export function removerTipoRubricaFixture(fx: TipoRubricaFixture): void {
  const saida = djangoShell(teardownScript(fx.mapeamentos));
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #319 não confirmou o teardown:\n${saida}`);
  }
}
