import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture das demandas do SGD (Issue #294).
 *
 * O `seed_demo` não cria demanda nenhuma, e só um ADT (o `adt` de
 * helpers/users.ts) é técnico de atividade dentro do próprio território. A
 * fixture monta, em nome dele:
 *
 * - `agendada`: atividade Agendada sem demandas — alvo da criação pela aba e
 *   pela busca do SGD;
 * - `comDemandas`: atividade com duas demandas em status diferentes;
 * - `outra`: atividade com uma demanda própria, para provar que a aba de uma
 *   atividade não lista a demanda da vizinha.
 *
 * Roda como `postgres`: `sgd_demand` tem row-level security, e o `app_user`
 * sem o contexto de sessão que o middleware define não enxerga nem grava
 * demanda nenhuma.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "DEMANDA_FIXTURE";

/** Prefixo de tudo que a fixture e os testes criam — é por ele que o teardown limpa. */
export const PREFIXO = "E2E-294";

export type DemandaFixture = {
  agendada: { id: number; titulo: string };
  comDemandas: {
    id: number;
    demandas: { id: number; titulo: string; status_display: string }[];
  };
  outra: { id: number; demanda: string };
  municipio: string;
  tecnico: string;
  tecnicoId: number;
  acao: { numero: string; descricao: string };
};

const SETUP_SCRIPT = `
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity
from apps.sgp.models.workplan import WorkPlanAcao

P = "${PREFIXO}"
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
perfil = adt.profiles.get(perfil__slug="adt-acr")
municipio = Municipality.objects.filter(territory_id=perfil.territorio_id).order_by("nome").first()
acao = WorkPlanAcao.objects.order_by("pk").first()
quando = timezone.now() + timedelta(days=15)

def atividade(titulo):
    return Activity.objects.create(
        titulo=titulo, tipo_atividade="oficina", acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="municipal", tecnico_responsavel=adt,
        data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
        descricao_narrativa="Criada pela fixture E2E da issue 294.",
    )

agendada = atividade(f"{P} Oficina agendada")
com = atividade(f"{P} Oficina com demandas")
d1 = Demand.objects.create(titulo=f"{P} Transporte da equipe", activity=com, solicitante=adt)
d2 = Demand.objects.create(titulo=f"{P} Material da oficina", activity=com, solicitante=adt, status="submetida")
outra = atividade(f"{P} Oficina vizinha")
Demand.objects.create(titulo=f"{P} Demanda da vizinha", activity=outra, solicitante=adt)

print("${MARCADOR}_SETUP " + json.dumps({
    "agendada": {"id": agendada.pk, "titulo": agendada.titulo},
    "comDemandas": {"id": com.pk, "demandas": [
        {"id": d.pk, "titulo": d.titulo, "status_display": d.get_status_display()} for d in (d1, d2)
    ]},
    "outra": {"id": outra.pk, "demanda": f"{P} Demanda da vizinha"},
    "municipio": municipio.nome,
    "tecnico": adt.nome,
    "tecnicoId": adt.pk,
    "acao": {"numero": acao.numero, "descricao": acao.descricao},
}))
`;

const TEARDOWN_SCRIPT = `
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity

P = "${PREFIXO}"
# Pelo PREFIXO, e nao por ids guardados: um run interrompido tambem sai limpo,
# e entram as atividades criadas pelos proprios testes (criacao inline).
atividades = Activity.all_objects.filter(titulo__startswith=P) if hasattr(Activity, "all_objects") else Activity.objects.filter(titulo__startswith=P)
Demand.objects.filter(activity__in=atividades).delete()
Demand.objects.filter(titulo__startswith=P).delete()
atividades.delete()
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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

export function criarDemandaFixture(): DemandaFixture {
  // Limpa sobras de um run interrompido antes de montar de novo.
  djangoShellComoDono(TEARDOWN_SCRIPT);
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) {
    throw new Error(`Fixture das demandas não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as DemandaFixture;
}

export function removerDemandaFixture(): void {
  djangoShellComoDono(TEARDOWN_SCRIPT);
}
