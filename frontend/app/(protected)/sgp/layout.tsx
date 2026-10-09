import { SgpChoicesProvider } from "@/app/providers/SgpChoicesProvider";

export default function SGPLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SgpChoicesProvider>{children}</SgpChoicesProvider>;
}
