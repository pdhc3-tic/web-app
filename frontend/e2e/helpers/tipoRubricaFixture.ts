import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do catálogo de tipos de solicitação (#365; a tela era a da #319).
 *
 * A spec cria um tipo novo ("Hospedagem") pela tela do Super Admin e o ADT o
 * solicita na montagem de uma demanda. A fixture:
 * - fotografa o catálogo (rubrica, situação, nome, ordem e schema de cada tipo);
 * - cria, em nome do ADT (Ewerton), uma atividade com uma demanda em Rascunho;
 * - devolve os tipos e as rubricas com os ids reais.
 *
 * O teardown apaga as demandas (e as solicitações) da fixture, os tipos que a
 * spec criou e devolve os do catálogo à foto. Roda como `postgres` (RLS de
 * `sgd_demand`).
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "TIPOS_365_FIXTURE";

export const PREFIXO_365 = "E2E-365";

export type TipoFoto = {
  id: number;
  slug: string;
  nome: string;
  rubrica: number;
  ativo: boolean;
  ordem: number;
  schema_campos: unknown;
};
export type RubricaFixture = { id: number; slug: string; nome: string; ativo: boolean };

export type TipoRubricaFixture = {
  tipos: TipoFoto[];
  rubricas: RubricaFixture[];
  demanda: { id: number; titulo: string };
};

const LIMPAR = `
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity

P = "${PREFIXO_365}"
Demand.objects.filter(titulo__startswith=P).delete()
Activity.objects.filter(titulo__startswith=P).delete()
`;

const SETUP_SCRIPT = `${LIMPAR}
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgd.models.tipo_solicitacao import TipoSolicitacao
from apps.sgd.services import demand as ds
from apps.sgp.budget.models import BudgetRubrica
from apps.sgp.models.workplan import WorkPlanAcao

adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Encontro de hospedagem solidária", tipo_atividade="intercambio",
    acao=WorkPlanAcao.objects.order_by("pk").first(), municipio=municipio, forma_atuacao="realizacao",
    ambito="territorial", tecnico_responsavel=adt, data_inicio=quando, data_fim=quando, status="agendado",
    criado_por=adt, descricao_narrativa="Criada pela fixture E2E da issue 365.",
)
demanda = ds.criar_demanda(titulo=f"{P} Hospedagem da comitiva", activity=atividade, justificativa="", solicitante=adt)

print("${MARCADOR}_SETUP " + json.dumps({
    "tipos": [
        {"id": t.pk, "slug": t.slug, "nome": t.nome, "rubrica": t.rubrica_id, "ativo": t.ativo,
         "ordem": t.ordem, "schema_campos": t.schema_campos}
        for t in TipoSolicitacao.objects.order_by("pk")
    ],
    "rubricas": [
        {"id": r.pk, "slug": r.slug, "nome": r.nome, "ativo": r.ativo}
        for r in BudgetRubrica.objects.order_by("nome")
    ],
    "demanda": {"id": demanda.pk, "titulo": demanda.titulo},
}))
`;

function teardownScript(foto: TipoFoto[]): string {
  return `${LIMPAR}
import json
from django.db import transaction
from apps.sgd.models.tipo_solicitacao import TipoSolicitacao

foto = json.loads(${JSON.stringify(JSON.stringify(foto))})
with transaction.atomic():
    # Tipo criado pela spec, já sem solicitação (as demandas da fixture saíram acima).
    TipoSolicitacao.objects.exclude(pk__in=[t["id"] for t in foto]).delete()
    for t in foto:
        TipoSolicitacao.objects.filter(pk=t["id"]).update(
            nome=t["nome"], rubrica_id=t["rubrica"], ativo=t["ativo"], ordem=t["ordem"],
            schema_campos=t["schema_campos"],
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

export function criarTipoRubricaFixture(): TipoRubricaFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #365 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as TipoRubricaFixture;
}

export function removerTipoRubricaFixture(fx: TipoRubricaFixture): void {
  const saida = djangoShell(teardownScript(fx.tipos));
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #365 não confirmou o teardown:\n${saida}`);
  }
}
