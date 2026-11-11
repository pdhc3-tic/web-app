"use client";

import { notFound } from "next/navigation";
import Link from "next/link";
import { documentoSpike } from "./documento";

export default function GovbrSpikePage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 p-6">
      <Link href="/styleguide" className="text-primary hover:underline">Voltar ao styleguide</Link>
      <h1 className="text-2xl font-semibold">Spike · GOV.BR DS + Tailwind</h1>
      <iframe
        title="Demonstração isolada de GOV.BR DS e Tailwind prefixado"
        srcDoc={documentoSpike}
        sandbox="allow-same-origin"
        className="h-[1100px] w-full rounded-lg border border-border bg-white"
        data-testid="govbr-spike-frame"
      />
    </main>
  );
}
