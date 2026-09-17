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
  /**
   * Atividade com a ficha inteira preenchida: UPF e membro participantes,
   * equipe adicional, coordenadas e parceiros em texto livre.
   *
   * Os campos escalares e a equipe são POSTOS pela fixture — o `seed_demo` os
   * deixa vazios, e sem eles não há como afirmar que a ficha renderiza cada um.
   * A UPF e o membro vêm do próprio seed: o vínculo entre eles é o que o teste
   * do link precisa, e forjá-lo esconderia justamente o que está sendo testado.
   */
  comFichaCompleta: number;
  /** UPF do membro participante — o destino esperado do link. */
  upfDoMembro: number;
  /** Id do membro participante cuja linha deve virar link. */
  membroParticipante: number;
  /** Valores gravados pela fixture, para o teste conferir o que está na tela. */
  latitude: string;
  longitude: string;
  parceirosLivres: string;
};

/** Coordenadas e parceiros gravados pela fixture — valores só dela. */
const LATITUDE = "-8.0476000";
const LONGITUDE = "-34.8770000";
const PARCEIROS_LIVRES = "Sindicato dos Trabalhadores Rurais de Serra Talhada";

const SETUP_SCRIPT = `
import json
from decimal import Decimal
from django.db.models import Count
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

# ── Ficha completa ───────────────────────────────────────────────────────────
# Uma atividade que ja tenha UPF E membro participantes. O vinculo membro->UPF
# vem do seed: e ele que o link da ficha precisa resolver, e cria-lo aqui
# testaria a fixture em vez da tela.
# O filtro por n_equipe evita mexer no M2M: o seed ja sorteia de 0 a 2 pessoas
# equipe adicional, entao basta ESCOLHER uma atividade que tenha, em vez de
# adicionar uma e ter de repor a lista original no teardown.
completa = None
for candidata in (
    Activity.objects.annotate(
        n_upfs=Count("upfs_participantes", distinct=True),
        n_membros=Count("membros_participantes", distinct=True),
        n_equipe=Count("equipe_adicional", distinct=True),
    )
    .filter(n_upfs__gt=0, n_membros__gt=0, n_equipe__gt=0, ativo=True)
    .exclude(pk__in=[com_evidencias.pk, com_erro.pk])
    .order_by("pk")
):
    membro = candidata.membros_participantes.filter(upf__isnull=False).first()
    if membro is not None:
        completa = candidata
        break

if completa is None:
    raise RuntimeError(
        "Nenhuma atividade com UPF, membro e equipe adicional: "
        "rode manage.py seed_demo --reset"
    )

completa.latitude = Decimal("${LATITUDE}")
completa.longitude = Decimal("${LONGITUDE}")
completa.parceiros_livres = "${PARCEIROS_LIVRES}"
completa.save(update_fields=["latitude", "longitude", "parceiros_livres"])

print("${MARCADOR}_SETUP " + json.dumps({
    "comEvidencias": com_evidencias.pk,
    "comErroDeAgenda": com_erro.pk,
    "comFichaCompleta": completa.pk,
    "upfDoMembro": membro.upf_id,
    "membroParticipante": membro.pk,
    "latitude": "${LATITUDE}",
    "longitude": "${LONGITUDE}",
    "parceirosLivres": "${PARCEIROS_LIVRES}",
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

# Desfaz o enriquecimento da ficha completa. Filtra pelo TEXTO que so a fixture
# grava, e nao por um id guardado: assim um run interrompido tambem sai limpo.
# So os tres escalares que a fixture gravou. Filtra pelo TEXTO que so ela usa, e
# nao por um id guardado: assim um run interrompido tambem sai limpo. O M2M da
# equipe adicional nao entra aqui porque a fixture nao o toca.
Activity.objects.filter(parceiros_livres="${PARCEIROS_LIVRES}").update(
    parceiros_livres="", latitude=None, longitude=None
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
