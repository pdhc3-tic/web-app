import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Ação crítica do Painel de Acompanhamento (#141), criada pelo model.
 *
 * Desde a #305 a Ação pertence a uma Submeta e a um Indicador, campos que o
 * formulário de Ações ainda não tem. Por isso a Ação nasce aqui, e não pela
 * tela: o spec do painel testa a apresentação do semáforo, não o cadastro.
 *
 * Período inteiro no passado e nenhuma Atividade: 0 de 100 contra 100%
 * esperado, vermelha e em atraso em qualquer data. O número é o da primeira
 * Submeta da Meta 1 com o sufixo `.99`, fora da faixa do seed.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PAINEL_141_FIXTURE";

export const DESCRICAO_ACAO_CRITICA = "Ação crítica do E2E do painel";

export type AcaoCritica = { id: number; numero: string };

const COMUM = `
from apps.sgp.models.workplan import WorkPlanAcao

def limpar():
    WorkPlanAcao.objects.filter(descricao="${DESCRICAO_ACAO_CRITICA}").delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import date
from apps.sgp.models import Indicator
from apps.sgp.models.workplan import WorkPlanSubmeta

limpar()
submeta = WorkPlanSubmeta.objects.filter(meta__numero=1).order_by("numero").first()
acao = WorkPlanAcao.objects.create(
    submeta=submeta, indicador=Indicator.objects.order_by("pk").first(),
    numero=f"{submeta.numero}.99", descricao="${DESCRICAO_ACAO_CRITICA}",
    quantidade_planejada=100, valor_unitario=10000,
    data_inicio=date(2024, 1, 1), data_fim=date(2024, 12, 31),
)
print("${MARCADOR}_SETUP " + json.dumps({"id": acao.pk, "numero": acao.numero}))
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

export function criarAcaoCritica(): AcaoCritica {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture da #141 não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as AcaoCritica;
}

export function removerAcaoCritica(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #141 não confirmou o teardown:\n${saida}`);
  }
}
