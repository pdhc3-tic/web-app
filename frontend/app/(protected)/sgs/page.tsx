import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SGSPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-cyan-700 dark:text-cyan-400">
        SGS — Sistema de Gestão de Serviços
      </h1>
    </div>
  );
}
