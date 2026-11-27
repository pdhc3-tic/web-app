import { execFileSync } from "node:child_process";
import path from "node:path";

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/**
 * Recria dispositivos, eventos e conflitos do SCA (`seed_demo --sca-only`).
 *
 * Roda como o dono do banco, como as outras fixtures. Como `app_user`, a RLS
 * esconde as UFPAs, o seed responde "Não há UFPAs no banco" e sai com código
 * 0 sem recriar nada (#478). Por isso, além do usuário, a saída é conferida:
 * sem a linha de resumo do seed, a fixture falha aqui, e não no meio do teste.
 */
export function recriarFixturesSca(): void {
  const saida = execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "backend",
      "sh",
      "-c",
      "DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD python manage.py seed_demo --sca-only",
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 120_000, stdio: ["ignore", "pipe", "pipe"] },
  );
  if (!/^SCA: .*conflitos/m.test(saida)) {
    throw new Error(`seed_demo --sca-only não recriou as fixtures do SCA:\n${saida}`);
  }
}
