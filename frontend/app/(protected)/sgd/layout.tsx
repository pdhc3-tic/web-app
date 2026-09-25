import { SgpChoicesProvider } from "@/app/providers/SgpChoicesProvider";

/**
 * O formulário de demanda (#294) cria atividade do SGP quando ela ainda não
 * existe, e o tipo de atividade vem dos choices do SGP.
 */
export default function SGDLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <SgpChoicesProvider>{children}</SgpChoicesProvider>;
}
