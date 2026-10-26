import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { AppShell } from "@/app/components/layout/AppShell";
import { Sidebar } from "@/app/components/layout/Sidebar";
import { ToastProvider } from "@/app/components/ui/Toast/Toast";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { SgpChoicesProvider } from "@/app/providers/SgpChoicesProvider";
import { ChoicesIndisponiveis } from "@/app/components/layout/ChoicesIndisponiveis";

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");
  return (
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
  );
}
