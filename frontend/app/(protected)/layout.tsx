import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { AppShell } from "@/app/components/layout/AppShell";
import { Sidebar } from "@/app/components/layout/Sidebar";

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");
  return <AppShell sidebar={<Sidebar />}>{children}</AppShell>;
}
