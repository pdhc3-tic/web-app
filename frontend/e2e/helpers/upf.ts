import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect } from "@playwright/test";

/**
 * Id da primeira UPF do `seed_demo`, lido direto do Postgres.
 *
 * A API não expõe um endpoint estável de "primeira UPF" e o seed randomiza os
 * dados a cada execução — consultar o banco é o jeito determinístico de ancorar
 * as specs que precisam de uma ficha existente.
 */
export function primeiroUpfId(): number {
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
      "select id from sgp_upf order by id limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed não criou nenhuma UPF").toBeGreaterThan(0);
  return id;
}

/** Id da primeira UPF que tem comunidade — para a edição pré-carregá-la. */
export function primeiraUpfComComunidadeId(): number {
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
      "select id from sgp_upf where comunidade_id is not null order by id limit 1;",
    ],
    { encoding: "utf8", timeout: 30_000 },
  ).trim();
  const id = Number(linha);
  expect(id, "seed não criou nenhuma UPF com comunidade").toBeGreaterThan(0);
  return id;
}

/** Prefixo do nome do titular das UPFs criadas pelo wizard no E2E. */
export const PREFIXO_UPF_E2E = "E2E-UPF-WIZARD";

/**
 * Apaga as UPFs (e os titulares) criadas pelo wizard no E2E. Como `postgres`,
 * o mesmo das outras fixtures (row-level security).
 */
export function removerUpfsDoWizard(): void {
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
from apps.sgp.cache import invalidate_upf_map_cache
from apps.sgp.models import UPF
from apps.sgp.models.membro import MembroFamilia

# UPF.titular (PROTECT) e MembroFamilia.upf (CASCADE) apontam um para o outro,
# e o delete() do Django recusa o ciclo. As FKs são DEFERRABLE INITIALLY
# DEFERRED: dentro da transação, os membros saem crus e a UPF sai pelo ORM,
# levando o resto das relações.
with transaction.atomic():
    upfs = UPF.all_objects.filter(titular__nome_completo__startswith="${PREFIXO_UPF_E2E}")
    ids = list(upfs.values_list("pk", flat=True))
    membros = MembroFamilia.objects.filter(upf_id__in=ids) | MembroFamilia.objects.filter(
        nome_completo__startswith="${PREFIXO_UPF_E2E}",
    )
    membros._raw_delete(membros.db)
    UPF.all_objects.filter(pk__in=ids).delete()
invalidate_upf_map_cache()
print("UPF_WIZARD_LIMPO")
`,
    ],
    { cwd: path.resolve(__dirname, "..", "..", ".."), encoding: "utf8", timeout: 120_000 },
  );
  if (!saida.includes("UPF_WIZARD_LIMPO")) {
    throw new Error(`Limpeza das UPFs do wizard não confirmou:\n${saida}`);
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
