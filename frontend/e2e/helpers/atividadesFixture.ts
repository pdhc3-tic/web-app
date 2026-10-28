import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Atividades reais para a `atividades.spec` (B6 da #302), uma por situação,
 * todas do Ewerton (ADT do RN) e com o prefixo `E2E-B6`:
 *
 * - `anexos`: em andamento, sem evidência — recebe a foto e o documento
 *   enviados pela tela;
 * - `semEvidencia`: em andamento, sem evidência — a tela barra a conclusão;
 * - `comFoto`: em andamento, com uma foto — conclui de verdade;
 * - `fotoRemovida`: em andamento, com uma foto que o teste desativa depois de
 *   abrir a ficha (como se outra aba a removesse): o backend recusa a conclusão;
 * - `pendente`: concluída sem evidência, para o filtro da listagem.
 *
 * O status é gravado direto no banco: o service só aceita criar em
 * Planejado/Agendado. `limpar()` roda no setup e no teardown e apaga também os
 * arquivos que a tela mandou para o storage local.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "ATIVIDADES_B6_FIXTURE";
export const PREFIXO_B6 = "E2E-B6";

export type Ref = { id: number; titulo: string };
export type AtividadesFixture = {
  anexos: Ref;
  semEvidencia: Ref;
  comFoto: Ref;
  fotoRemovida: Ref;
  pendente: Ref;
};

const COMUM = `
from apps.core.storage import get_storage
from apps.sgp.models import Activity
from apps.sgp.models.activity_document import ActivityDocument
from apps.sgp.models.activity_photo import ActivityPhoto

def limpar():
    atividades = Activity.all_objects.filter(titulo__startswith="${PREFIXO_B6}")
    storage = get_storage()
    for modelo in (ActivityPhoto, ActivityDocument):
        for anexo in modelo.all_objects.filter(activity__in=atividades):
            if anexo.arquivo_key and not anexo.arquivo_key.startswith("e2e/"):
                try:
                    storage.delete_object(anexo.arquivo_key)
                except Exception:
                    pass
    atividades.delete()
`;

const SETUP_SCRIPT = `${COMUM}
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Municipality
from apps.sgp.models.workplan import WorkPlanAcao

limpar()
adt = get_user_model().objects.get(email="ewerton.bandeira@demo.pdhc.local")
territorio_id = adt.profiles.get(perfil__slug="adt-acr").territorio_id
municipio = Municipality.objects.filter(territory_id=territorio_id).order_by("nome").first()
acao = WorkPlanAcao.objects.order_by("pk").first()
ontem = timezone.now() - timedelta(days=1)

def atividade(titulo, status, foto=False):
    a = Activity.objects.create(
        titulo=f"${PREFIXO_B6} {titulo}", tipo_atividade="intercambio", acao=acao, municipio=municipio,
        forma_atuacao="realizacao", ambito="territorial", tecnico_responsavel=adt,
        data_inicio=ontem, data_fim=ontem, status="agendado", criado_por=adt,
        descricao_narrativa="Criada pela fixture E2E da B6 da issue 302.",
    )
    Activity.all_objects.filter(pk=a.pk).update(status=status)
    if foto:
        ActivityPhoto.objects.create(
            activity=a, arquivo_key=f"e2e/b6-{a.pk}.jpg", arquivo_url=f"http://localhost:8080/media/e2e/b6-{a.pk}.jpg",
            ordem=0, content_type="image/jpeg", tamanho_bytes=1024, criado_por=adt,
        )
    return {"id": a.pk, "titulo": a.titulo}

print("${MARCADOR}_SETUP " + json.dumps({
    "anexos": atividade("Oficina para anexar evidências", "em_andamento"),
    "semEvidencia": atividade("Visita ainda sem evidência", "em_andamento"),
    "comFoto": atividade("Mutirão com foto", "em_andamento", foto=True),
    "fotoRemovida": atividade("Feira com a foto removida", "em_andamento", foto=True),
    "pendente": atividade("Reunião concluída sem evidência", "concluido_sem_evidencia"),
}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
limpar()
print("${MARCADOR}_TEARDOWN_OK")
`;

/** Como `postgres`, o mesmo das outras fixtures (row-level security). */
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

export function criarAtividadesFixture(): AtividadesFixture {
  const saida = djangoShell(SETUP_SCRIPT);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_SETUP `));
  if (!linha) throw new Error(`Fixture das atividades não confirmou o setup:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_SETUP `.length)) as AtividadesFixture;
}

export function removerAtividadesFixture(): void {
  const saida = djangoShell(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture das atividades não confirmou o teardown:\n${saida}`);
  }
}

/** Desativa as fotos da atividade, como a remoção feita em outra aba. */
export function desativarFotos(atividadeId: number): void {
  const saida = djangoShell(`
from apps.sgp.models.activity_photo import ActivityPhoto
for foto in ActivityPhoto.objects.filter(activity_id=${Number(atividadeId)}):
    foto.soft_delete()
print("${MARCADOR}_FOTOS_OFF")
`);
  if (!saida.includes(`${MARCADOR}_FOTOS_OFF`)) {
    throw new Error(`Não foi possível desativar as fotos:\n${saida}`);
  }
}

/** Anexos ativos gravados no backend para a atividade. */
export function contarAnexos(atividadeId: number): { fotos: number; documentos: number } {
  const saida = djangoShell(`
import json
from apps.sgp.models.activity_document import ActivityDocument
from apps.sgp.models.activity_photo import ActivityPhoto
print("${MARCADOR}_ANEXOS " + json.dumps({
    "fotos": ActivityPhoto.objects.filter(activity_id=${Number(atividadeId)}).count(),
    "documentos": ActivityDocument.objects.filter(activity_id=${Number(atividadeId)}).count(),
}))
`);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR}_ANEXOS `));
  if (!linha) throw new Error(`Não foi possível contar os anexos:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_ANEXOS `.length));
}
