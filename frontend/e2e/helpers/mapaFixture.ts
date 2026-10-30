import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * UPFs reais para o mapa (B6 da #302): 201 UPFs com coordenadas a poucos
 * metros umas das outras, num município sem nenhuma UPF do seed. Passam do
 * limite de 200 marcadores do `MapViewClient`, então o mapa agrupa em clusters.
 * Também devolve um segundo município sem UPF, para o estado vazio.
 *
 * O `/upfs/mapa/` guarda a resposta em cache por 60 s; a fixture invalida o
 * cache ao criar e ao limpar, como o backend faz ao salvar uma UPF.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "MAPA_B6_FIXTURE";
export const PREFIXO_MAPA = "E2E-B6-MAPA";
export const TOTAL_UPFS_MAPA = 201;

export type MapaFixture = { municipio: number; municipioVazio: number };

const LIMPAR = `
from apps.sgp.cache import invalidate_upf_map_cache
from apps.sgp.models import UPF
from apps.sgp.models.membro import MembroFamilia

def limpar():
    UPF.all_objects.filter(titular__nome_completo__startswith="${PREFIXO_MAPA}").delete()
    MembroFamilia.objects.filter(nome_completo__startswith="${PREFIXO_MAPA}").delete()
    invalidate_upf_map_cache()
`;

const SETUP_SCRIPT = `${LIMPAR}
import json
from decimal import Decimal
from apps.core.models import Municipality

limpar()
base = UPF.objects.filter(ativo=True).order_by("pk").first()
usados = UPF.all_objects.values_list("municipio_id", flat=True)
municipio, vazio = Municipality.objects.exclude(pk__in=usados).order_by("pk")[:2]
membros = MembroFamilia.objects.bulk_create(
    [MembroFamilia(nome_completo=f"${PREFIXO_MAPA} Titular {i:03d}", cpf=f"9{i:010d}") for i in range(${TOTAL_UPFS_MAPA})],
)
UPF.objects.bulk_create([
    UPF(projeto_id=base.projeto_id, comunidade_id=base.comunidade_id, titular=m, municipio=municipio,
        territorio_id=base.territorio_id,
        latitude=Decimal("-5.795000") + Decimal(i) * Decimal("0.000010"),
        longitude=Decimal("-35.209000") + Decimal(i) * Decimal("0.000010"))
    for i, m in enumerate(membros)
])
invalidate_upf_map_cache()
print("${MARCADOR}_SETUP " + json.dumps({"municipio": municipio.pk, "municipioVazio": vazio.pk}))
`;

const TEARDOWN_SCRIPT = `${LIMPAR}
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

export function criarMapaFixture(): MapaFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture do mapa não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as MapaFixture;
}

export function removerMapaFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture do mapa não confirmou o teardown:\n${saida}`);
  }
}
