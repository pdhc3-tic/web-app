"use client";

import { formatCurrencyBRL } from "@/app/lib/format";
import type { LimiteGasto, PerfilOperacional } from "@/app/lib/limites";
import type { Rubrica } from "@/app/lib/tiposSolicitacao";

type Props = {
  rubricas: Rubrica[];
  perfis: PerfilOperacional[];
  padroes: LimiteGasto[];
  editavel: boolean;
  onDefinir: (perfil: PerfilOperacional, rubrica: Rubrica) => void;
  onAlterar: (limite: LimiteGasto, perfil: PerfilOperacional) => void;
};

const TH = "px-4 py-2.5 text-left text-2xs font-medium uppercase tracking-[0.06em] text-text-muted";
const TD = "px-4 py-3 align-middle";

/**
 * Aba "Padrão por perfil" (#400): rubricas nas linhas, perfis operacionais nas
 * colunas — duas colunas cabem no celular; seis não caberiam. Cada célula é o
 * valor que toda pessoa do perfil recebe na rubrica, no período exibido.
 */
export function MatrizPadroes({ rubricas, perfis, padroes, editavel, onDefinir, onAlterar }: Props) {
  const doPerfil = (perfil: PerfilOperacional, rubrica: Rubrica) =>
    padroes.find((l) => l.perfil === perfil.id && l.rubrica === rubrica.id) ?? null;

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-sm" data-testid="limites-matriz">
        <thead className="border-b border-border bg-surface-muted/50">
          <tr>
            <th className={TH}>Rubrica</th>
            {perfis.map((p) => (
              <th key={p.id} className={`${TH} text-right`}>
                {p.nome}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rubricas.map((r) => (
            <tr key={r.id} className="border-b border-border last:border-b-0">
              <td className={`${TD} font-medium text-text`}>{r.nome}</td>
              {perfis.map((p) => {
                const limite = doPerfil(p, r);
                return (
                  <td
                    key={p.id}
                    className={`${TD} text-right`}
                    data-testid={`limites-celula-${p.slug}-${r.slug}`}
                  >
                    <div className="flex items-center justify-end gap-3">
                      <span
                        className={`tabular-nums ${limite ? "text-text" : "text-text-muted"}`}
                        title={limite?.justificativa || undefined}
                        data-testid="limites-celula-valor"
                      >
                        {limite ? formatCurrencyBRL(limite.valor_limite) : "Sem padrão"}
                      </span>
                      {editavel && (
                        <button
                          type="button"
                          onClick={() => (limite ? onAlterar(limite, p) : onDefinir(p, r))}
                          className="text-xs text-primary hover:underline focus-visible:outline-2 focus-visible:outline-primary"
                          aria-label={`${limite ? "Alterar" : "Definir"} o padrão de ${p.nome} em ${r.nome}`}
                          data-testid="limites-celula-acao"
                        >
                          {limite ? "Alterar" : "Definir"}
                        </button>
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
