"use client";

import { Pencil, Power, Trash2 } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Chip } from "@/app/components/ui/Chip/Chip";
import {
  CATEGORIA_LABEL,
  DESAGREGACAO_LABEL,
  FORMA_APURACAO_LABEL,
  rotulo,
  UNIDADE_MEDIDA_LABEL,
  type Indicador,
} from "@/app/lib/indicadores";
import { odsShortLabel } from "@/app/lib/metas";

const TH =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const acaoBtn =
  "inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

type Props = {
  indicadores: Indicador[];
  carregando: boolean;
  /** UGP e Super Admin: editar, inativar e excluir. */
  canManage: boolean;
  onEditar: (i: Indicador) => void;
  onAlternarAtivo: (i: Indicador) => void;
  onExcluir: (i: Indicador) => void;
};

function Traco() {
  return <span className="text-text-muted">—</span>;
}

function Ods({ ids }: { ids: number[] }) {
  if (!ids.length) return <Traco />;
  return (
    <div className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <Chip key={id}>{odsShortLabel(id)}</Chip>
      ))}
    </div>
  );
}

/** `sufixo` separa os botões do cartão (celular) dos da tabela: os dois ficam no DOM. */
function Acoes({
  indicador,
  onEditar,
  onAlternarAtivo,
  onExcluir,
  sufixo = "",
}: Omit<Props, "indicadores" | "carregando" | "canManage"> & { indicador: Indicador; sufixo?: string }) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label={`Editar indicador ${indicador.codigo}`}
        onClick={() => onEditar(indicador)}
        className={acaoBtn}
        data-testid={`indicador-editar-${indicador.id}${sufixo}`}
      >
        <Pencil className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label={`${indicador.ativo ? "Inativar" : "Reativar"} indicador ${indicador.codigo}`}
        title={indicador.ativo ? "Inativar" : "Reativar"}
        onClick={() => onAlternarAtivo(indicador)}
        className={acaoBtn}
        data-testid={`indicador-ativo-${indicador.id}${sufixo}`}
      >
        <Power className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label={`Excluir indicador ${indicador.codigo}`}
        onClick={() => onExcluir(indicador)}
        className={`${acaoBtn} hover:bg-error-bg hover:text-error-text`}
        data-testid={`indicador-excluir-${indicador.id}${sufixo}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Tabela do catálogo (desktop) e cartões (celular), no formato da listagem de Metas. */
export function IndicadoresTable({ indicadores, carregando, canManage, ...acoes }: Props) {
  if (carregando) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 text-sm text-text-muted" role="status">
        Carregando o catálogo…
      </div>
    );
  }

  return (
    <div data-testid="indicadores-table">
      <div className="relative hidden overflow-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Catálogo de Indicadores do Plano de Trabalho.</caption>
          <thead>
            <tr>
              <th scope="col" className={TH}>Código</th>
              <th scope="col" className={TH}>Nome</th>
              <th scope="col" className={TH}>Unidade</th>
              <th scope="col" className={TH}>Forma de apuração</th>
              <th scope="col" className={TH}>Categoria</th>
              <th scope="col" className={TH}>ODS</th>
              <th scope="col" className={TH}>Desagregação</th>
              <th scope="col" className={TH}>Situação</th>
              {canManage && (
                <th scope="col" className={TH}>
                  <span className="sr-only">Ações</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {indicadores.map((i) => (
              <tr key={i.id} className="border-t border-border align-top" data-testid={`indicador-linha-${i.id}`}>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-text">{i.codigo}</td>
                <td className="min-w-48 px-4 py-3 text-text">{i.nome}</td>
                <td className="whitespace-nowrap px-4 py-3 text-text">{rotulo(UNIDADE_MEDIDA_LABEL, i.unidade_medida)}</td>
                <td className="min-w-40 px-4 py-3 text-text">{rotulo(FORMA_APURACAO_LABEL, i.forma_apuracao)}</td>
                <td className="px-4 py-3 text-text">{rotulo(CATEGORIA_LABEL, i.categoria) || <Traco />}</td>
                <td className="px-4 py-3"><Ods ids={i.ods_ids ?? []} /></td>
                <td className="px-4 py-3 text-text">
                  {(i.desagregacoes ?? []).map((d) => rotulo(DESAGREGACAO_LABEL, d)).join(", ") || <Traco />}
                </td>
                <td className="px-4 py-3">
                  <Badge status={i.ativo ? "ativo" : "inativo"} label={i.ativo ? "Ativo" : "Inativo"} />
                </td>
                {canManage && (
                  <td className="px-2 py-2">
                    <Acoes indicador={i} {...acoes} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {indicadores.map((i) => (
          <li key={i.id} className="rounded-lg border border-border bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-text-muted">{i.codigo}</p>
                <p className="text-sm font-medium text-text">{i.nome}</p>
              </div>
              <Badge status={i.ativo ? "ativo" : "inativo"} label={i.ativo ? "Ativo" : "Inativo"} />
            </div>
            <p className="mt-2 text-xs text-text-muted">
              {rotulo(UNIDADE_MEDIDA_LABEL, i.unidade_medida)} · {rotulo(FORMA_APURACAO_LABEL, i.forma_apuracao)}
            </p>
            {canManage && (
              <div className="mt-3 flex justify-end">
                <Acoes indicador={i} {...acoes} sufixo="-cartao" />
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
