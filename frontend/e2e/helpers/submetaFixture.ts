import { execFileSync } from "node:child_process";
import path from "node:path";
import { SLOT_NUMERO, freeMetaSlot, restoreMetaSlot } from "./metaSlot";

/**
 * Meta sem Submetas para o fluxo da #431: Meta → nova Submeta → nova Ação.
 *
 * O `seed_demo` ocupa os sete números de Meta, e as dele já têm Submetas. A
 * fixture libera o slot {@link SLOT_NUMERO} (ver `metaSlot.ts`), cria nele uma
 * Meta vazia e, no fim, apaga o que o teste cadastrou nela (Ações e Submetas)
 * antes de devolver o slot à Meta original.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "SUBMETA_431";

export type MetaSemSubmetas = { id: number; numero: number; inicio: string; fim: string };

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", script],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

const CRIAR = (submetas: number) => `
import json
from datetime import date
from apps.core.models import User
from apps.sgp.models import WorkPlanMeta

autor = User.objects.filter(profiles__perfil__slug="ugp").first()
meta = WorkPlanMeta.objects.create(
    numero=${SLOT_NUMERO},
    titulo="E2E-431 Meta sem Submetas",
    descricao="Criada pelo E2E da #431.",
    data_inicio=date(2026, 1, 1),
    data_fim=date(2027, 12, 31),
    criado_por=autor,
)
from apps.sgp.models import WorkPlanSubmeta
# Submetas já existentes, para o caso de mais de uma página da API (revisão do PR #434).
WorkPlanSubmeta.objects.bulk_create([
    WorkPlanSubmeta(
        meta=meta, numero=f"${SLOT_NUMERO}.{i}", titulo=f"E2E-431 Submeta {i}",
        data_inicio=date(2026, 1, 1), data_fim=date(2027, 12, 31),
    )
    for i in range(1, ${submetas} + 1)
])
print("${MARCADOR} " + json.dumps({"id": meta.pk, "numero": meta.numero, "inicio": "2026-01-01", "fim": "2027-12-31"}))
`;

const LIMPAR = `
from apps.sgp.models import WorkPlanAcao, WorkPlanMeta, WorkPlanSubmeta

for meta in WorkPlanMeta.objects.filter(numero=${SLOT_NUMERO}, titulo__startswith="E2E-431"):
    WorkPlanAcao.objects.filter(submeta__meta=meta).delete()
    WorkPlanSubmeta.objects.filter(meta=meta).delete()
    meta.delete()
print("${MARCADOR}_LIMPO")
`;

/** `submetas` > 0 cria a Meta já com as Submetas X.1 a X.N. */
export function criarMetaSemSubmetas(submetas = 0): MetaSemSubmetas {
  // Um run interrompido pode ter deixado a Meta do teste no slot.
  djangoShell(LIMPAR);
  freeMetaSlot();
  const saida = djangoShell(CRIAR(submetas));
  const linha = saida.split("\n").map((l) => l.trim()).find((l) => l.startsWith(`${MARCADOR} `));
  if (!linha) throw new Error(`Não consegui criar a Meta do teste:\n${saida}`);
  return JSON.parse(linha.slice(MARCADOR.length + 1));
}

export function removerMetaSemSubmetas(): void {
  const saida = djangoShell(LIMPAR);
  if (!saida.includes(`${MARCADOR}_LIMPO`)) throw new Error(`Falha ao limpar a Meta do teste:\n${saida}`);
  restoreMetaSlot();
}
