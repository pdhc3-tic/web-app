import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SGDPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-emerald-700 dark:text-emerald-400">
        SGD — Sistema de Gestão de Documentos
      </h1>
    </div>
  );
}
