import { auth, signOut } from "@/auth";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const session = await auth();

  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            Dashboard
          </h1>
          <form
            action={async () => {
              "use server";
              await signOut({ redirectTo: "/login" });
            }}
          >
            <button
              type="submit"
              className="h-9 px-4 rounded-full border border-zinc-200 dark:border-zinc-700 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              Sair
            </button>
          </form>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-xl border border-zinc-200 dark:border-zinc-700 p-6 space-y-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-1">
              Usuário
            </p>
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
              {session.user.username}
            </p>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-1">
              E-mail
            </p>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              {session.user.email || "—"}
            </p>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-2">
              Permissões
            </p>
            {(session.user.permissions ?? []).length === 0 ? (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Nenhuma permissão atribuída.</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {(session.user.permissions ?? []).map((perm) => (
                  <li
                    key={perm}
                    className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-700 text-xs text-zinc-700 dark:text-zinc-300 font-mono"
                  >
                    {perm}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
