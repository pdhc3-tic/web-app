import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SCAPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-blue-700 dark:text-blue-400">
        SCA — Sistema de Controle e Acompanhamento
      </h1>
    </div>
  );
}
