import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SGFPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-amber-700 dark:text-amber-400">
        SGF — Sistema de Gestão Financeira
      </h1>
    </div>
  );
}
