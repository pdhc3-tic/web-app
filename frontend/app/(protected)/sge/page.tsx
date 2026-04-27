import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SGEPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-purple-700 dark:text-purple-400">
        SGE — Sistema de Gestão de Estoque
      </h1>
    </div>
  );
}
