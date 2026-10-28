import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Dados reais para os testes das exportações assíncronas (#240, A4 da #302).
 *
 * - `criarUpfsEmVolume`: 1.001 UPFs sintéticas, para a listagem passar do
 *   limite síncrono do backend (`UPF_EXPORT_ASYNC_THRESHOLD`, 1.000 por
 *   padrão) e o `/upfs/exportar/` responder 202 de verdade.
 * - `criarJob`: um `ExportJob` do usuário num estado que o fluxo normal não
 *   para tempo suficiente para o teste observar: em `erro`, `pendente` (sem
 *   ir para a fila) ou concluído com o arquivo vencido.
 * - `marcoDosJobs` / `apagarJobsDesde`: o teardown apaga os jobs que a spec
 *   gerou, pelo maior id existente no início.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "EXPORTACAO_FIXTURE";
const PREFIXO_UPFS = "E2E-240";

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

/** Roda o script e devolve o que ele imprimiu depois de `${MARCADOR} `. */
function executar(script: string): string {
  const saida = djangoShell(`${script}\n`);
  const linha = saida.split("\n").find((l) => l.startsWith(`${MARCADOR} `));
  if (linha === undefined) throw new Error(`Fixture de exportação não confirmou:\n${saida}`);
  return linha.slice(MARCADOR.length + 1).trim();
}

const LIMPAR_UPFS = `
from apps.sgp.models import UPF
from apps.sgp.models.membro import MembroFamilia
UPF.all_objects.filter(titular__nome_completo__startswith="${PREFIXO_UPFS}").delete()
MembroFamilia.objects.filter(nome_completo__startswith="${PREFIXO_UPFS}").delete()
`;

export function criarUpfsEmVolume(): number {
  return Number(
    executar(`${LIMPAR_UPFS}
base = UPF.objects.filter(ativo=True).order_by("pk").first()
membros = MembroFamilia.objects.bulk_create(
    [MembroFamilia(nome_completo=f"${PREFIXO_UPFS} Titular {i:04d}", cpf=f"{i:011d}") for i in range(1, 1002)],
    batch_size=500,
)
UPF.objects.bulk_create(
    [UPF(projeto_id=base.projeto_id, comunidade_id=base.comunidade_id, titular=m,
         municipio_id=base.municipio_id, territorio_id=base.territorio_id) for m in membros],
    batch_size=500,
)
print("${MARCADOR}", UPF.objects.filter(titular__nome_completo__startswith="${PREFIXO_UPFS}").count())`),
  );
}

export function removerUpfsEmVolume(): void {
  executar(`${LIMPAR_UPFS}\nprint("${MARCADOR}", "ok")`);
}

export type EstadoDoJob = "erro" | "pendente" | "expirado";

/** Cria um job do usuário no estado pedido e devolve o id. Não vai para a fila. */
export function criarJob(email: string, tipo: "plano_trabalho" | "atividades" | "upfs", estado: EstadoDoJob): number {
  return Number(
    executar(`
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.sgp.models import ExportJob
agora = timezone.now()
dados = {
    "erro": {"status": "erro", "erro": "O worker não conseguiu gerar o arquivo."},
    "pendente": {"status": "pendente", "enfileirado_em": agora},
    "expirado": {"status": "concluida", "progresso": 100, "conteudo": b"x", "concluido_em": agora - timedelta(days=2),
                 "expira_em": agora - timedelta(days=1), "nome_arquivo": "${tipo}_expirado.csv", "content_type": "text/csv"},
}["${estado}"]
job = ExportJob.objects.create(
    tipo="${tipo}", formato="csv", filtros={}, solicitante=get_user_model().objects.get(email="${email}"), **dados,
)
print("${MARCADOR}", job.pk)`),
  );
}

export function apagarJob(id: number): void {
  executar(`
from apps.sgp.models import ExportJob
ExportJob.objects.filter(pk=${id}).delete()
print("${MARCADOR}", "ok")`);
}

/** O maior id de job existente agora: tudo acima dele foi criado pela spec. */
export function marcoDosJobs(): number {
  return Number(
    executar(`
from django.db.models import Max
from apps.sgp.models import ExportJob
print("${MARCADOR}", ExportJob.objects.aggregate(m=Max("pk"))["m"] or 0)`),
  );
}

export function apagarJobsDesde(marco: number): void {
  executar(`
from apps.sgp.models import ExportJob
ExportJob.objects.filter(pk__gt=${marco}).delete()
print("${MARCADOR}", "ok")`);
}
