import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da diária sem valor vigente (#440).
 *
 * Para não apagar os valores das faixas que as outras specs usam, cria uma
 * faixa só desta spec, ativa e sem valor na tabela, e enquadra nela um
 * município do Território RN. Para esse município, a simulação e a gravação da
 * diária são recusadas ("Sem valor de diária vigente para a faixa …"), como em
 * produção com a tabela vazia (#439).
 *
 * Também cria a atividade e a demanda em Rascunho do ADT Ewerton, de onde o
 * formulário é aberto. O teardown apaga tudo, inclusive o valor que o teste
 * cadastra na faixa pela tela. Roda como `postgres` por causa do RLS.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PDHC_E2E_DIARIA_SEM_VALOR";
const PREFIXO = "E2E-440";

export const FAIXA_NOME = `${PREFIXO} Faixa sem valor`;

export type DiariasSemValorFixture = {
  demandaId: number;
  faixaId: number;
  municipioNome: string;
};

const COMUM = `
from apps.sgp.models import Activity
from apps.sgd.models.approval_step import ApprovalStep
from apps.sgd.models.demand import Demand
from apps.sgd.models.diarias import EnquadramentoFaixaDiaria, FaixaDestinoDiaria, TabelaDiaria

P = "${PREFIXO}"

def limpar():
    demandas = Demand.objects.filter(titulo__startswith=P)
    ApprovalStep.objects.filter(demanda__in=demandas).delete()
    demandas.delete()
    Activity.objects.filter(titulo__startswith=P).delete()
    faixas = FaixaDestinoDiaria.objects.filter(nome__startswith=P)
    TabelaDiaria.objects.filter(faixa_destino__in=faixas).delete()
    faixas.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao
from apps.sgd.services import demand as ds

limpar()
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
enquadrados = EnquadramentoFaixaDiaria.objects.values_list("codigo_ibge", flat=True)
# O segundo do território em diante: o primeiro é o destino das diárias da montar-demanda.
municipio = (
    Municipality.objects.filter(territory_id=territorio_id).exclude(codigo_ibge__in=enquadrados)
    .order_by("nome")[1]
)
faixa = FaixaDestinoDiaria.objects.create(nome="${FAIXA_NOME}", ordem=99, ativo=True)
EnquadramentoFaixaDiaria.objects.create(faixa=faixa, codigo_ibge=municipio.codigo_ibge, nome_referencia=municipio.nome)

quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Visita ao assentamento", tipo_atividade="intercambio", acao=WorkPlanAcao.objects.order_by("pk").first(),
    municipio=municipio, forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 440.",
)
demanda = ds.criar_demanda(titulo=f"{P} Diárias da visita", activity=atividade, justificativa="", solicitante=adt)
print("${MARCADOR}_SETUP " + json.dumps({"demandaId": demanda.pk, "faixaId": faixa.pk, "municipioNome": municipio.nome}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

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

export function criarDiariasSemValorFixture(): DiariasSemValorFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Falha ao montar a fixture da #440:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as DiariasSemValorFixture;
}

export function removerDiariasSemValorFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Falha ao remover a fixture da #440:\n${saida}`);
  }
}
