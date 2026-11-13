import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do "slot" de Meta usado pelo teste de criação.
 *
 * `WorkPlanMeta.numero` é 1–7 e único, e o `seed_demo` já ocupa os sete
 * números: sem liberar um deles, não há como criar uma Meta pela tela. Este
 * helper libera o número {@link SLOT_NUMERO} antes do teste e devolve o estado
 * original depois.
 *
 * A Meta original NÃO é apagada: desde a Submeta (#305) ela é dona de
 * submetas (`WorkPlanSubmeta.meta` é PROTECT), e as Ações apontam para a Meta e
 * para a Submeta ao mesmo tempo. A fixture só "estaciona" o número dela fora
 * da faixa (o 1–7 é validação do Django, não constraint do banco), por um
 * `update` que não passa pelos validadores. Submetas, Ações e Atividades não se
 * mexem; no restore, a Meta criada pelo teste sai e a original volta ao número.
 */
export const SLOT_NUMERO = 7;
/** Número fora da faixa de 1 a 7 onde a Meta original espera o teste acabar. */
const NUMERO_ESTACIONADO = 900 + SLOT_NUMERO;

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

const FREE_SCRIPT = `
from apps.sgp.models import WorkPlanMeta

SLOT, ESTACIONADO = ${SLOT_NUMERO}, ${NUMERO_ESTACIONADO}

# Run anterior interrompido: a original já está estacionada, e o que estiver
# no slot foi criado por um teste.
if WorkPlanMeta.objects.filter(numero=ESTACIONADO).exists():
    WorkPlanMeta.objects.filter(numero=SLOT, submetas__isnull=True, acoes__isnull=True).delete()
WorkPlanMeta.objects.filter(numero=SLOT).update(numero=ESTACIONADO)

if WorkPlanMeta.objects.filter(numero=SLOT).exists():
    raise RuntimeError("o slot da Meta continua ocupado")
print("SLOT_FREE_OK")
`;

const RESTORE_SCRIPT = `
from apps.sgp.models import WorkPlanMeta

SLOT, ESTACIONADO = ${SLOT_NUMERO}, ${NUMERO_ESTACIONADO}

if not WorkPlanMeta.objects.filter(numero=ESTACIONADO).exists():
    # Nada foi estacionado por nós: não mexer no banco.
    print("SLOT_RESTORE_SKIP")
else:
    # A Meta que o teste criou no slot nasce sem submetas nem Ações.
    WorkPlanMeta.objects.filter(numero=SLOT, submetas__isnull=True, acoes__isnull=True).delete()
    WorkPlanMeta.objects.filter(numero=ESTACIONADO).update(numero=SLOT)
    print("SLOT_RESTORE_OK")
`;

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", script],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

/** Libera o número {@link SLOT_NUMERO} para que a UI consiga criar a Meta. */
export function freeMetaSlot(): void {
  const saida = djangoShell(FREE_SCRIPT);
  if (!saida.includes("SLOT_FREE_OK")) {
    throw new Error(`Falha ao liberar o slot da Meta:\n${saida}`);
  }
}

/** Apaga a Meta criada pelo teste e devolve a Meta original ao número dela. */
export function restoreMetaSlot(): void {
  const saida = djangoShell(RESTORE_SCRIPT);
  if (!saida.includes("SLOT_RESTORE_OK") && !saida.includes("SLOT_RESTORE_SKIP")) {
    throw new Error(`Falha ao restaurar o slot da Meta:\n${saida}`);
  }
}
