import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { AppShell } from "@/app/components/layout/AppShell";
import { Sidebar } from "@/app/components/layout/Sidebar";
import { ToastProvider } from "@/app/components/ui/Toast/Toast";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { SgpChoicesProvider } from "@/app/providers/SgpChoicesProvider";
import { ChoicesIndisponiveis } from "@/app/components/layout/ChoicesIndisponiveis";
import SessionProvider from "@/app/providers/SessionProvider";

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");
  return (
    // A sessão lida aqui segue para o cliente: a useSession() começa pronta e o
    // apiClient já tem o token, sem ida a /api/auth/session ao abrir a tela (#448).
    <SessionProvider session={session}>
      <QueryProvider>
        <ToastProvider>
          {/* Choices do SGP para toda a área logada: SGP, SGD e SCA (#272). */}
          <SgpChoicesProvider>
            <AppShell sidebar={<Sidebar />}>
              <ChoicesIndisponiveis />
              {children}
            </AppShell>
          </SgpChoicesProvider>
        </ToastProvider>
      </QueryProvider>
    </SessionProvider>
  );
}
