import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect } from "@playwright/test";

/**
 * Id da primeira UFPA do `seed_demo`, lido direto do Postgres.
 *
 * A API não expõe um endpoint estável de "primeira UFPA" e o seed randomiza os
 * dados a cada execução — consultar o banco é o jeito determinístico de ancorar
 * as specs que precisam de uma ficha existente.
 */
export function primeiroUfpaId(): number {
  const linha = execFileSync(
    "docker",
    [
      "exec",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "app_db",
      "-tAc",
      "select id from sgp_ufpa order by id limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed não criou nenhuma UFPA").toBeGreaterThan(0);
  return id;
}

/** Id da primeira UFPA que tem comunidade — para a edição pré-carregá-la. */
export function primeiraUfpaComComunidadeId(): number {
  const linha = execFileSync(
    "docker",
    [
      "exec",
      "db",
      "psql",
      "-U",
      "postgres",
      "-d",
      "app_db",
      "-tAc",
      "select id from sgp_ufpa where comunidade_id is not null order by id limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed não criou nenhuma UFPA com comunidade").toBeGreaterThan(0);
  return id;
}

/** Prefixo do nome do titular das UFPAs criadas pelo wizard no E2E. */
export const PREFIXO_UFPA_E2E = "E2E-UFPA-WIZARD";

/**
 * Apaga as UFPAs (e os titulares) criadas pelo wizard no E2E. Como `postgres`,
 * o mesmo das outras fixtures (row-level security).
 */
export function removerUfpasDoWizard(): void {
  const saida = execFileSync(
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
      `
from django.db import transaction
from apps.sgp.cache import invalidate_ufpa_map_cache
from apps.sgp.models import UFPA
from apps.sgp.models.membro import MembroFamilia

# UFPA.titular (PROTECT) e MembroFamilia.ufpa (CASCADE) apontam um para o outro,
# e o delete() do Django recusa o ciclo. As FKs são DEFERRABLE INITIALLY
# DEFERRED: dentro da transação, os membros saem crus e a UFPA sai pelo ORM,
# levando o resto das relações.
with transaction.atomic():
    ufpas = UFPA.all_objects.filter(titular__nome_completo__startswith="${PREFIXO_UFPA_E2E}")
    ids = list(ufpas.values_list("pk", flat=True))
    membros = MembroFamilia.objects.filter(ufpa_id__in=ids) | MembroFamilia.objects.filter(
        nome_completo__startswith="${PREFIXO_UFPA_E2E}",
    )
    membros._raw_delete(membros.db)
    UFPA.all_objects.filter(pk__in=ids).delete()
invalidate_ufpa_map_cache()
print("UFPA_WIZARD_LIMPO")
`,
    ],
    { cwd: path.resolve(__dirname, "..", "..", ".."), encoding: "utf8", timeout: 120_000 },
  );
  if (!saida.includes("UFPA_WIZARD_LIMPO")) {
    throw new Error(`Limpeza das UFPAs do wizard não confirmou:\n${saida}`);
  }
}

/** CPF válido gerado a partir de nove dígitos aleatórios. */
export function cpfValido(): string {
  const base = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
  if (base.every((d) => d === base[0])) base[8] = (base[0] + 1) % 10;
  const digito = (numeros: number[]) => {
    const soma = numeros.reduce((acc, d, i) => acc + d * (numeros.length + 1 - i), 0);
    const resto = (soma * 10) % 11;
    return resto === 10 ? 0 : resto;
  };
  const d1 = digito(base);
  const d2 = digito([...base, d1]);
  return [...base, d1, d2].join("");
}
