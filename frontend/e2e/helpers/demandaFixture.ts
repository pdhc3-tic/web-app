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
 * - `completa`: atividade com comunidade, para o contexto herdado completo;
 * - `comDemandas`: atividade com duas demandas em status diferentes;
 * - `outra`: atividade com uma demanda própria, para provar que a aba de uma
 *   atividade não lista a demanda da vizinha;
 * - `custo` (#404): atividade com custo e riscos de glosa conhecidos. Uma
 *   demanda Submetida com R$ 1.200 estimados (custo previsto) e uma Concluída
 *   com R$ 800 autorizados e R$ 950 pagos (custo realizado de R$ 800, o
 *   autorizado). A concluída tem os dois riscos que o backend registraria: o
 *   pago acima do autorizado (R$ 150, como `registrar_pagamento` grava) e o
 *   de demanda sem evidência (R$ 950, pelo próprio
 *   `registrar_demanda_sem_evidencia`). Um terceiro risco, já resolvido, na
 *   solicitação da Submetida, não pode aparecer na ficha.
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
  completa: { id: number; titulo: string; comunidade: string };
  comDemandas: {
    id: number;
    demandas: { id: number; titulo: string; status_display: string }[];
  };
  outra: { id: number; demanda: string };
  custo: {
    id: number;
    riscos: { pagoAcima: number; semEvidencia: number; resolvido: number };
  };
  municipio: string;
  tecnico: string;
  tecnicoId: number;
  acao: { numero: string; descricao: string };
  territorio: string;
  meta: { numero: number; titulo: string };
  submeta: { numero: string; titulo: string };
  indicador: { codigo: string; nome: string; unidade_medida: string };
};

const SETUP_SCRIPT = `
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity, Comunidade
from apps.sgp.models.workplan import WorkPlanAcao

P = "${PREFIXO}"
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
perfil = adt.profiles.get(perfil__slug="adt-acr")
municipio = Municipality.objects.filter(territory_id=perfil.territorio_id).order_by("nome").first()
acao = WorkPlanAcao.objects.order_by("pk").first()
quando = timezone.now() + timedelta(days=15)

def atividade(titulo, comunidade=None):
    return Activity.objects.create(
        titulo=titulo, tipo_atividade="oficina", acao=acao, municipio=municipio, comunidade=comunidade,
        forma_atuacao="realizacao", ambito="municipal", tecnico_responsavel=adt,
        data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
        descricao_narrativa="Criada pela fixture E2E da issue 294.",
    )

agendada = atividade(f"{P} Oficina agendada")
comunidade = Comunidade.objects.create(nome=f"{P} Sítio Lajedo", municipio=municipio, criada_por=adt)
completa = atividade(f"{P} Roda de conversa", comunidade)
com = atividade(f"{P} Oficina com demandas")
# Abrangência do solicitante, como a criação pelo serviço grava (#352).
from apps.sgd.services.contexto import abrangencia_para_nova_demanda
UF, TERRITORIO = abrangencia_para_nova_demanda(solicitante=adt)
d1 = Demand.objects.create(titulo=f"{P} Transporte da equipe", activity=com, solicitante=adt, estado_sigla=UF, territorio=TERRITORIO)
d2 = Demand.objects.create(titulo=f"{P} Material da oficina", activity=com, solicitante=adt, status="submetida", estado_sigla=UF, territorio=TERRITORIO)
outra = atividade(f"{P} Oficina vizinha")

# #404: custo previsto e realizado e riscos de glosa conhecidos.
from decimal import Decimal
from django.db import transaction
from django.utils import timezone as tz
from apps.sgd.models.demand_request import DemandRequest
from apps.sgd.services import demand as ds
from apps.sgd.services.workflow import registrar_demanda_sem_evidencia
from apps.sgp.models import GlosaRisk

custo = atividade(f"{P} Oficina com custo e riscos")
CAMPOS = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-11-20T08:00",
    "data_hora_devolucao": "2026-11-21T18:00", "destino_rota": "Sede → comunidade",
    "estimativa_km": 120, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 10,
}

def com_solicitacao(titulo, valor):
    d = Demand.objects.create(titulo=f"{P} {titulo}", activity=custo, solicitante=adt, estado_sigla=UF, territorio=TERRITORIO)
    with transaction.atomic():
        s = ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=CAMPOS, valor_estimado=Decimal(valor))
    return d, s

aberta, sol_aberta = com_solicitacao("Van para a oficina", "1200")
Demand.objects.filter(pk=aberta.pk).update(status="submetida")
paga, sol = com_solicitacao("Van da visita", "800")
DemandRequest.objects.filter(pk=sol.pk).update(valor_autorizado=Decimal("800"), valor_pago=Decimal("950"))
Demand.objects.filter(pk=paga.pk).update(status="concluida")
paga.refresh_from_db()
paga.recalcular_totais()

def risco(demanda, solicitacao, **campos):
    return GlosaRisk.objects.create(
        entidade=GlosaRisk.ENTIDADE_DEMANDA, entidade_id=str(demanda.pk), activity_id=custo.pk,
        demanda_id=str(demanda.pk), demand_request_id=str(solicitacao.pk), criado_por=adt, **campos,
    )

pago_acima = risco(
    paga, sol, tipo_situacao=GlosaRisk.Tipo.PAGO_ACIMA_AUTORIZADO, severidade=GlosaRisk.Severidade.ALTA,
    valor_autorizado=Decimal("800"), valor_pago=Decimal("950"), valor_exposto=Decimal("150"),
)
registrar_demanda_sem_evidencia(paga, usuario=adt)
sem_evidencia = GlosaRisk.objects.get(tipo_situacao=GlosaRisk.Tipo.DEMANDA_SEM_EVIDENCIA, demanda_id=str(paga.pk))
# Um só risco de pago acima por solicitação (uniq_glosarisk_solicitacao_import): o
# resolvido fica na solicitação da outra demanda.
resolvido = risco(
    aberta, sol_aberta, tipo_situacao=GlosaRisk.Tipo.PAGO_ACIMA_AUTORIZADO, severidade=GlosaRisk.Severidade.MEDIA,
    valor_autorizado=Decimal("800"), valor_pago=Decimal("870"), valor_exposto=Decimal("70"),
)
GlosaRisk.objects.filter(pk=resolvido.pk).update(resolvido_em=tz.now())
Demand.objects.create(titulo=f"{P} Demanda da vizinha", activity=outra, solicitante=adt, estado_sigla=UF, territorio=TERRITORIO)

print("${MARCADOR}_SETUP " + json.dumps({
    "agendada": {"id": agendada.pk, "titulo": agendada.titulo},
    "completa": {"id": completa.pk, "titulo": completa.titulo, "comunidade": comunidade.nome},
    "comDemandas": {"id": com.pk, "demandas": [
        {"id": d.pk, "titulo": d.titulo, "status_display": d.get_status_display()} for d in (d1, d2)
    ]},
    "outra": {"id": outra.pk, "demanda": f"{P} Demanda da vizinha"},
    "custo": {"id": custo.pk, "riscos": {
        "pagoAcima": pago_acima.pk, "semEvidencia": sem_evidencia.pk, "resolvido": resolvido.pk,
    }},
    "municipio": municipio.nome,
    "tecnico": adt.nome,
    "tecnicoId": adt.pk,
    "acao": {"numero": acao.numero, "descricao": acao.descricao},
    "territorio": municipio.territory.nome,
    "meta": {"numero": acao.meta.numero, "titulo": acao.meta.titulo},
    "submeta": {"numero": acao.submeta.numero, "titulo": acao.submeta.titulo},
    "indicador": {
        "codigo": acao.indicador.codigo, "nome": acao.indicador.nome,
        "unidade_medida": acao.indicador.unidade_medida,
    },
}))
`;

const TEARDOWN_SCRIPT = `
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity, Comunidade, GlosaRisk

P = "${PREFIXO}"
# Pelo PREFIXO, e nao por ids guardados: um run interrompido tambem sai limpo,
# e entram as atividades criadas pelos proprios testes (criacao inline).
atividades = Activity.all_objects.filter(titulo__startswith=P) if hasattr(Activity, "all_objects") else Activity.objects.filter(titulo__startswith=P)
demandas = Demand.objects.filter(activity__in=atividades) | Demand.objects.filter(titulo__startswith=P)
# O risco de glosa guarda a demanda por referência fraca: não sai em cascata.
GlosaRisk.objects.filter(demanda_id__in=[str(pk) for pk in demandas.values_list("pk", flat=True)]).delete()
Demand.objects.filter(activity__in=atividades).delete()
Demand.objects.filter(titulo__startswith=P).delete()
atividades.delete()
Comunidade.objects.filter(nome__startswith=P).delete()
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
