"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { qk } from "@/app/lib/queryKeys";
import {
  AVISO_NAO_RETROAGE,
  ERRO_DUPLICADO,
  conflitoDeAtivo,
  listRubricas,
  type MapeamentoPayload,
  type MapeamentoTipoRubrica,
} from "@/app/lib/tipoRubrica";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";

type Props = {
  /** `null` = novo mapeamento. */
  editando: MapeamentoTipoRubrica | null;
  /** Todos os ativos, para a regra do duplicado. */
  mapeamentos: readonly MapeamentoTipoRubrica[];
  onClose: () => void;
  onSalvar: (payload: MapeamentoPayload) => Promise<void>;
};

/**
 * Novo e Editar. Os tipos vêm do `/choices/` (`solicitacao_tipo`); as
 * rubricas, de `GET /sgp/rubricas/`. Na edição o tipo fica fixo: mudar de
 * tipo é outro mapeamento.
 */
export function MapeamentoForm({ editando, mapeamentos, onClose, onSalvar }: Props) {
  const choices = useSgpChoices();
  const [tipo, setTipo] = useState(editando?.tipo ?? "");
  const [rubrica, setRubrica] = useState(editando ? String(editando.rubrica) : "");
  const [ativo, setAtivo] = useState(editando?.ativo ?? true);
  const [erros, setErros] = useState<{ tipo?: string; rubrica?: string }>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const rubricas = useQuery({
    queryKey: qk.configSgd.rubricas,
    queryFn: ({ signal }) => listRubricas(signal),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const opcoesRubrica: SelectOption[] = useMemo(() => {
    const opcoes = (rubricas.data ?? [])
      .filter((r) => r.ativo || String(r.id) === rubrica)
      .map((r) => ({ value: String(r.id), label: r.nome }));
    // A rubrica atual do mapeamento em edição aparece mesmo sem o catálogo.
    if (editando && !opcoes.some((o) => o.value === String(editando.rubrica))) {
      opcoes.unshift({ value: String(editando.rubrica), label: editando.rubrica_nome });
    }
    return opcoes;
  }, [rubricas.data, rubrica, editando]);

  const conflito = ativo && tipo ? conflitoDeAtivo(mapeamentos, tipo, editando?.id ?? null) : null;
  const erroTipo = conflito ? `${ERRO_DUPLICADO} Hoje ele usa ${conflito.rubrica_nome}.` : erros.tipo;

  async function salvar() {
    const faltando: typeof erros = {};
    if (!tipo) faltando.tipo = "Escolha o tipo de solicitação.";
    if (!rubrica) faltando.rubrica = "Escolha a rubrica.";
    setErros(faltando);
    // O duplicado é barrado aqui, antes de chamar a API.
    if (conflito || Object.keys(faltando).length > 0) return;

    setSalvando(true);
    setErroGeral(null);
    try {
      await onSalvar({ tipo, rubrica: Number(rubrica), ativo });
    } catch (e) {
      if (e instanceof ApiError) {
        const porCampo: typeof erros = {};
        for (const fe of e.fieldErrors ?? []) {
          if (fe.field === "tipo" || fe.field === "rubrica") porCampo[fe.field] = fe.message;
        }
        setErros(porCampo);
        if (Object.keys(porCampo).length === 0) setErroGeral(e.message);
      } else {
        setErroGeral("Não foi possível salvar o mapeamento.");
      }
    } finally {
      setSalvando(false);
    }
  }

  return (
    <SlideOver
      open
      onClose={salvando ? () => {} : onClose}
      title={editando ? "Editar mapeamento" : "Novo mapeamento"}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={salvar} loading={salvando} data-testid="mapeamento-salvar">
            Salvar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-4 py-4" data-testid="mapeamento-form">
        <Select
          id="mapeamento-tipo"
          label="Tipo de solicitação"
          required
          options={choices.solicitacao_tipo}
          value={tipo}
          onChange={(v) => {
            setTipo(v);
            setErros((atual) => ({ ...atual, tipo: undefined }));
          }}
          placeholder="Selecione o tipo"
          disabled={!!editando}
          error={erroTipo}
        />

        <Select
          id="mapeamento-rubrica"
          label="Rubrica"
          required
          options={opcoesRubrica}
          value={rubrica}
          onChange={(v) => {
            setRubrica(v);
            setErros((atual) => ({ ...atual, rubrica: undefined }));
          }}
          placeholder={rubricas.isPending ? "Carregando rubricas…" : "Selecione a rubrica"}
          error={
            erros.rubrica ??
            (rubricas.isError ? "Não foi possível carregar as rubricas do orçamento." : undefined)
          }
        />

        <label className="flex items-start gap-2 text-sm text-text">
          <input
            type="checkbox"
            checked={ativo}
            onChange={(e) => setAtivo(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-(--color-primary)"
            data-testid="mapeamento-ativo"
          />
          <span>
            Ativo
            <span className="block text-xs text-text-muted">
              Só um mapeamento ativo por tipo. Os inativos ficam como histórico.
            </span>
          </span>
        </label>

        <p className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {AVISO_NAO_RETROAGE}
        </p>

        {erroGeral && (
          <p role="alert" className="text-sm text-error-text" data-testid="mapeamento-erro">
            {erroGeral}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
