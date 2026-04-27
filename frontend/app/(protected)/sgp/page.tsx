import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function SGPPage() {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
      <h1 className="text-4xl font-bold text-rose-700 dark:text-rose-400">
        SGP — Sistema de Gestão de Pessoas
      </h1>
    </div>
  );
}
