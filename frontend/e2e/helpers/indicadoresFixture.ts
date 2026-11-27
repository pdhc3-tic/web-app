import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do Catálogo de Indicadores (#453).
 *
 * Os indicadores que a suíte cria, edita e exclui têm código com o prefixo
 * `E2E453-`, e o teardown apaga os que sobrarem. Para os bloqueios do backend
 * (409 de "em uso" e de recálculo) a suíte usa um indicador do seed que já tem
 * Ação vinculada, sem gravar nada nele: ela vê a recusa e cancela.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "PDHC_E2E_INDICADORES";
export const PREFIXO = "E2E453-";

export type IndicadorEmUso = { id: number; codigo: string; formaApuracao: string; acoes: number };

const LIMPAR = `
from apps.sgp.models.indicator import Indicator
Indicator.objects.filter(codigo__startswith="${PREFIXO}").delete()
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
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Limpa as sobras de um run interrompido e devolve um indicador do seed com Ações. */
export function criarIndicadoresFixture(): IndicadorEmUso {
  const saida = djangoShell(`${LIMPAR}
import json
from django.db.models import Count
emuso = (
    Indicator.objects.filter(ativo=True).annotate(n=Count("acoes")).filter(n__gt=0).order_by("-n", "codigo").first()
)
if emuso is None:
    raise RuntimeError("Nenhum indicador com Ação vinculada: rode seed_demo --reset")
print("${MARCADOR}_SETUP " + json.dumps({
    "id": emuso.pk, "codigo": emuso.codigo, "formaApuracao": emuso.forma_apuracao, "acoes": emuso.n,
}))
`);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Falha ao montar a fixture de indicadores:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as IndicadorEmUso;
}

export function removerIndicadoresFixture(): void {
  const saida = djangoShell(`${LIMPAR}\nprint("${MARCADOR}_TEARDOWN_OK")`);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) throw new Error(`Falha ao limpar indicadores:\n${saida}`);
}

/** O indicador no banco pelo código: nome, forma, ativo — ou null se não existe. */
export function indicadorNoBanco(codigo: string): { nome: string; forma: string; ativo: boolean } | null {
  const saida = djangoShell(`
import json
from apps.sgp.models.indicator import Indicator
i = Indicator.objects.filter(codigo="${codigo}").first()
print("${MARCADOR}_LIDO " + json.dumps(None if i is None else {"nome": i.nome, "forma": i.forma_apuracao, "ativo": i.ativo}))
`);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_LIDO `));
  if (!linha) throw new Error(`Falha ao ler o indicador:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_LIDO `.length));
}
