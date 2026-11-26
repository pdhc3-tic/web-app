import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Descoberta, só leitura, das atividades do `seed_demo` que a #464 confere
 * (`atividades-ficha-filtros.spec.ts`). Nada é gravado: a spec só lê.
 *
 * - `vazia`: sem coordenadas, parceiros, participantes e resultados — a ficha
 *   tem de mostrar o "—" e os avisos em vez de esconder as seções.
 * - `comDemandaConcluida`: atividade com uma demanda concluída, a única em que
 *   a aba Demandas mostra o valor executado.
 * - `filtros`: Meta, Submeta e Indicador com atividades e as contagens que a
 *   lista deve devolver para cada filtro.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "FICHA_464";

const SCRIPT = `
import json
from apps.sgd.models import Demand
from apps.sgp.models import Activity

vazia = (
    Activity.objects.filter(
        ativo=True,
        latitude__isnull=True,
        parceiros_livres="",
        parceiros_organizacoes__isnull=True,
        ufpas_participantes__isnull=True,
        membros_participantes__isnull=True,
        resultados_alcancados="",
    )
    .order_by("id")
    .values_list("id", flat=True)
    .first()
)
concluida = Demand.objects.filter(status="concluida").order_by("id").values_list("activity_id", flat=True).first()

# Filtros (#464): a Submeta com mais atividades, a Meta dela e um Indicador de
# outra Meta, com as contagens que a lista da UGP (escopo nacional) deve ter.
from django.db.models import Count
ativas = Activity.objects.filter(ativo=True)
sub = ativas.values("acao__submeta_id", "acao__meta_id").annotate(n=Count("id")).order_by("-n", "acao__submeta_id").first()
ind = (
    ativas.exclude(acao__meta_id=sub["acao__meta_id"])
    .values("acao__indicador_id").annotate(n=Count("id")).order_by("-n", "acao__indicador_id").first()
)
filtros = {
    "total": ativas.count(),
    "meta": sub["acao__meta_id"],
    "nMeta": ativas.filter(acao__meta_id=sub["acao__meta_id"]).count(),
    "submeta": sub["acao__submeta_id"],
    "nSubmeta": sub["n"],
    "indicador": ind["acao__indicador_id"],
    "nIndicador": ind["n"],
    "nMetaEIndicador": ativas.filter(acao__meta_id=sub["acao__meta_id"], acao__indicador_id=ind["acao__indicador_id"]).count(),
}
print("${MARCADOR} " + json.dumps({"vazia": vazia, "comDemandaConcluida": concluida, "filtros": filtros}))
`;

export type FiltrosDoPlano = {
  /** Atividades ativas: o que a UGP, de escopo nacional, vê sem filtro. */
  total: number;
  meta: number;
  nMeta: number;
  submeta: number;
  nSubmeta: number;
  /** Indicador com atividades fora da Meta acima: o filtro combinado restringe de verdade. */
  indicador: number;
  nIndicador: number;
  nMetaEIndicador: number;
};

export type FichaAtividadeFixture = { vazia: number; comDemandaConcluida: number; filtros: FiltrosDoPlano };

/** Como `postgres`, o mesmo das outras fixtures (row-level security). */
export function descobrirAtividadesDaFicha(): FichaAtividadeFixture {
  const saida = execFileSync(
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
      SCRIPT,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR} `));
  if (!linha) throw new Error(`Não foi possível descobrir as atividades da ficha:\n${saida}`);
  const fx = JSON.parse(linha.slice(MARCADOR.length + 1)) as Partial<FichaAtividadeFixture>;
  if (!fx.vazia || !fx.comDemandaConcluida) {
    throw new Error(`O seed não tem as atividades esperadas: ${JSON.stringify(fx)}`);
  }
  return fx as FichaAtividadeFixture;
}
