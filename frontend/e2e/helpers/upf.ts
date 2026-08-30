import { execFileSync } from "node:child_process";
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
