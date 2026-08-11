import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture do "slot" de Meta usado pelo teste de criação.
 *
 * `WorkPlanMeta.numero` é 1–7 e único, e o `seed_demo` já ocupa os sete
 * números — sem liberar um deles não existe criação possível pela UI. Este
 * helper libera o número {@link SLOT_NUMERO} antes do teste e devolve o estado
 * original depois.
 *
 * A liberação NÃO apaga Ações: `Activity.acao` é PROTECT, então as Ações da
 * Meta são estacionadas em outra Meta e trazidas de volta no restore — as
 * Atividades continuam apontando para as mesmas linhas o tempo todo.
 */
export const SLOT_NUMERO = 7;

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const STATE_FILE = "/tmp/e2e_meta_slot.json";

const FREE_SCRIPT = `
import json
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta

SLOT = ${SLOT_NUMERO}
STATE = "${STATE_FILE}"

meta = WorkPlanMeta.objects.filter(numero=SLOT).first()
estado = None

if meta is not None:
    estado = {
        "titulo": meta.titulo,
        "descricao": meta.descricao,
        "ods_ids": meta.ods_ids,
        "data_inicio": str(meta.data_inicio),
        "data_fim": str(meta.data_fim),
        "criado_por_id": meta.criado_por_id,
        "acao_ids": list(meta.acoes.values_list("pk", flat=True)),
    }
    if estado["acao_ids"]:
        abrigo = WorkPlanMeta.objects.exclude(pk=meta.pk).order_by("numero").first()
        if abrigo is None:
            raise RuntimeError("nao ha outra Meta para estacionar as Acoes")
        WorkPlanAcao.objects.filter(pk__in=estado["acao_ids"]).update(meta_id=abrigo.pk)
    meta.delete()

with open(STATE, "w") as f:
    json.dump(estado, f)

print("SLOT_FREE_OK")
`;

const RESTORE_SCRIPT = `
import json
import os
from datetime import date

from apps.sgp.models import WorkPlanAcao, WorkPlanMeta

SLOT = ${SLOT_NUMERO}
STATE = "${STATE_FILE}"

if not os.path.exists(STATE):
    # Sem arquivo de estado nada foi liberado por nós: não mexer no banco.
    print("SLOT_RESTORE_SKIP")
else:
    with open(STATE) as f:
        estado = json.load(f)
    os.remove(STATE)

    # Remove a Meta que o teste criou no slot (nasce sem Ações vinculadas).
    WorkPlanMeta.objects.filter(numero=SLOT).delete()

    if estado is not None:
        meta = WorkPlanMeta.objects.create(
            numero=SLOT,
            titulo=estado["titulo"],
            descricao=estado["descricao"],
            ods_ids=estado["ods_ids"],
            data_inicio=date.fromisoformat(estado["data_inicio"]),
            data_fim=date.fromisoformat(estado["data_fim"]),
            criado_por_id=estado["criado_por_id"],
        )
        if estado["acao_ids"]:
            WorkPlanAcao.objects.filter(pk__in=estado["acao_ids"]).update(meta_id=meta.pk)

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

/** Apaga a Meta criada pelo teste e recoloca a Meta original com suas Ações. */
export function restoreMetaSlot(): void {
  const saida = djangoShell(RESTORE_SCRIPT);
  if (!saida.includes("SLOT_RESTORE_OK") && !saida.includes("SLOT_RESTORE_SKIP")) {
    throw new Error(`Falha ao restaurar o slot da Meta:\n${saida}`);
  }
}
