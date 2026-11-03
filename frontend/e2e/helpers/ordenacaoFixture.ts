import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da ordenação por valor da listagem (#364).
 *
 * Uma atividade do ADT (Ewerton) com três demandas em Rascunho, cada uma com
 * uma solicitação de valor diferente. O `valor_estimado_total` sai do
 * `recalcular_totais()` do próprio serviço, como no uso real. A criação fora
 * de ordem de valor (1800, 500, 3200) faz a ordem padrão (`-criado_em`) ser
 * diferente das duas ordenações por valor, então cada estado é distinguível.
 *
 * Rascunho não reserva saldo nem consome limite individual: a fixture não
 * mexe em orçamento. A spec filtra a lista pela atividade (recorte do #297)
 * para não depender das demandas que outras specs deixam no banco.
 *
 * Roda como `postgres`: `sgd_demand` tem row-level security.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ORDENACAO_FIXTURE";

export const PREFIXO = "E2E-364";

export type OrdenacaoFixture = {
  atividadeId: number;
  /** Na ordem de criação: 1800, 500, 3200. */
  demandas: { id: number; titulo: string; valor: string }[];
};

const TEARDOWN_SCRIPT = `
from apps.sgd.models.demand import Demand
from apps.sgp.models import Activity

P = "${PREFIXO}"
Demand.objects.filter(titulo__startswith=P).delete()
Activity.objects.filter(titulo__startswith=P).delete()
print("${MARCADOR}_TEARDOWN_OK")
`;

const SETUP_SCRIPT = `${TEARDOWN_SCRIPT}
import json
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgd.services import demand as ds
from apps.sgp.models.workplan import WorkPlanAcao

adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
acao = WorkPlanAcao.objects.order_by("pk").first()
quando = timezone.now() + timedelta(days=20)
atividade = Activity.objects.create(
    titulo=f"{P} Intercâmbio com três deslocamentos", tipo_atividade="intercambio", acao=acao,
    municipio=municipio, forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
    data_inicio=quando, data_fim=quando, status="agendado", criado_por=adt,
    descricao_narrativa="Criada pela fixture E2E da issue 364.",
)
CAMPOS = {
    "tipo_veiculo": "van", "data_hora_retirada": "2026-12-10T08:00",
    "data_hora_devolucao": "2026-12-11T18:00", "destino_rota": "Caicó → Mossoró",
    "estimativa_km": 280, "motorista_incluso": True, "combustivel_incluso": True,
    "numero_passageiros": 12,
}
demandas = []
for titulo, valor in (("Van da ida", "1800"), ("Van do apoio local", "500"), ("Van da comitiva", "3200")):
    d = ds.criar_demanda(titulo=f"{P} {titulo}", activity=atividade, justificativa="", solicitante=adt)
    ds.adicionar_solicitacao(d, tipo="veiculo", campos_json=CAMPOS, valor_estimado=Decimal(valor))
    d.refresh_from_db()
    assert d.valor_estimado_total == Decimal(valor), d.valor_estimado_total
    demandas.append({"id": d.pk, "titulo": d.titulo, "valor": valor})

print("${MARCADOR}_SETUP " + json.dumps({"atividadeId": atividade.pk, "demandas": demandas}))
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

export function criarOrdenacaoFixture(): OrdenacaoFixture {
  const saida = djangoShellComoDono(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) {
    throw new Error(`Fixture da ordenação não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as OrdenacaoFixture;
}

export function removerOrdenacaoFixture(): void {
  djangoShellComoDono(TEARDOWN_SCRIPT);
}
