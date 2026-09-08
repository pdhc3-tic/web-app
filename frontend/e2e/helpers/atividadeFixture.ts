import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da ficha de Atividade (Issue #233).
 *
 * Duas coisas que o `seed_demo` não entrega prontas:
 *
 * 1. **Uma atividade com evidências.** O seed distribui fotos e documentos por
 *    sorteio, então nem toda atividade tem as duas coisas. A fixture DESCOBRE
 *    uma que tenha, em vez de fixar um id que muda a cada re-seed.
 *
 * 2. **Uma atividade com o sync do Google Calendar em erro.** O seed grava
 *    todas como `ok` — o estado de erro só aparece quando a integração falha de
 *    verdade. A fixture marca uma e devolve ao estado anterior no teardown.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const MARCADOR = "ATIVIDADE_FIXTURE";

export type AtividadeFixture = {
  /** Atividade com pelo menos uma foto E um documento. */
  comEvidencias: number;
  /** Atividade marcada com `google_calendar_sync_status = "erro"`. */
  comErroDeAgenda: number;
};

const SETUP_SCRIPT = `
import json
from django.db.models import Count, Q
from apps.sgp.models import Activity

com_evidencias = (
    Activity.objects.annotate(
        n_fotos=Count("fotos", distinct=True),
        n_docs=Count("documentos", distinct=True),
    )
    .filter(n_fotos__gt=0, n_docs__gt=0, ativo=True)
    .order_by("pk")
    .first()
)
if com_evidencias is None:
    raise RuntimeError(
        "Nenhuma atividade com foto E documento: rode manage.py seed_demo --reset"
    )

# Uma atividade DIFERENTE recebe o erro de agenda, para que o teste do badge
# nao dependa da que carrega as evidencias (e vice-versa).
com_erro = (
    Activity.objects.filter(ativo=True)
    .exclude(pk=com_evidencias.pk)
    .order_by("pk")
    .first()
)
Activity.objects.filter(pk=com_erro.pk).update(google_calendar_sync_status="erro")

print("${MARCADOR}_SETUP " + json.dumps({
    "comEvidencias": com_evidencias.pk,
    "comErroDeAgenda": com_erro.pk,
}))
`;

/**
 * Devolve TODAS as atividades ao estado `ok`.
 *
 * Mais amplo do que "desfaz o que criei" de propósito: `ok` é o que o
 * `seed_demo` grava em todas, então repor esse estado é idempotente e não
 * deixa resíduo caso um run anterior tenha sido interrompido.
 */
const TEARDOWN_SCRIPT = `
from apps.sgp.models import Activity

Activity.objects.exclude(google_calendar_sync_status="ok").update(
    google_calendar_sync_status="ok"
)
print("${MARCADOR}_TEARDOWN_OK")
`;

function djangoShell(script: string): string {
  return execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "manage.py", "shell", "-c", script],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000 },
  );
}

export function criarAtividadeFixture(): AtividadeFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_SETUP `));

  if (!linha) {
    throw new Error(`Fixture da atividade não confirmou o setup:\n${saida}`);
  }
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as AtividadeFixture;
}

export function removerAtividadeFixture(): void {
  djangoShell(TEARDOWN_SCRIPT);
}
