"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  baixarPlanoTrabalho,
  ExportTimeoutError,
  FORMATO_OPTIONS,
  type FormatoExport,
} from "@/app/lib/exportarPlano";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Mesmas opções do filtro do painel. */
  metaOptions: SelectOption[];
  /** Meta filtrada no painel — a exportação nasce alinhada com a tela. */
  metaIdInicial: string;
  /** Território filtrado no painel; segue junto sem aparecer no formulário. */
  territorioId: string;
  /** Há filtro de Situação ativo? O endpoint não aceita esse recorte. */
  situacaoAtiva: boolean;
};

export function ExportarModal({
  open,
  onClose,
  metaOptions,
  metaIdInicial,
  territorioId,
  situacaoAtiva,
}: Props) {
  const { showToast } = useToast();

  const [formato, setFormato] = useState<FormatoExport>("csv");
  const [meta, setMeta] = useState(metaIdInicial);
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Cada abertura reflete o filtro vigente do painel e esquece o erro da
  // tentativa anterior. Ajuste durante a renderização — e não em efeito —
  // porque não há sistema externo a sincronizar, só estado derivado de prop.
  const [abertoAnterior, setAbertoAnterior] = useState(open);
  if (open !== abertoAnterior) {
    setAbertoAnterior(open);
    if (open) {
      setMeta(metaIdInicial);
      setErro(null);
    }
  }

  function fechar() {
    if (gerando) return;
    setErro(null);
    onClose();
  }

  async function handleConfirmar() {
    if (gerando) return;

    // Mesma regra do WorkPlanExportQuerySerializer.validate — barrar aqui evita
    // uma ida ao servidor para receber de volta o que já se sabe.
    if (inicio && fim && inicio > fim) {
      setErro("O início do período não pode ser posterior ao fim.");
      return;
    }

    setErro(null);
    setGerando(true);
    try {
      const nome = await baixarPlanoTrabalho({
        formato,
        meta_id: meta || undefined,
        territorio_id: territorioId || undefined,
        periodo_inicio: inicio || undefined,
        periodo_fim: fim || undefined,
      });
      showToast(`Download de ${nome} iniciado.`);
      onClose();
    } catch (e: unknown) {
      if (e instanceof ExportTimeoutError) {
        setErro(
          "A geração do arquivo passou de 60 segundos e foi interrompida. " +
            "Tente de novo filtrando uma Meta ou um período menor.",
        );
      } else if (e instanceof ApiError) {
        setErro(e.message);
      } else {
        setErro(
          "Não foi possível exportar o Plano de Trabalho. Tente novamente.",
        );
      }
    } finally {
      setGerando(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={fechar}
      title="Exportar Plano de Trabalho"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            onClick={fechar}
            disabled={gerando}
            data-testid="exportar-cancelar"
          >
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={handleConfirmar}
            loading={gerando}
            leftIcon={<Download className="h-4 w-4" />}
            data-testid="exportar-confirmar"
          >
            Exportar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4 p-4" data-testid="exportar-modal">
        <p className="text-sm text-text-muted">
          O arquivo traz uma linha por Ação, com quantidades, valores e
          semáforo, dentro do seu escopo territorial.
        </p>

        <div data-testid="exportar-formato">
          <Select
            label="Formato"
            required
            options={FORMATO_OPTIONS}
            value={formato}
            onChange={(v) => setFormato(v as FormatoExport)}
            disabled={gerando}
          />
        </div>

        <div data-testid="exportar-meta">
          <Select
            label="Meta"
            options={[{ value: "", label: "Todas as Metas" }, ...metaOptions]}
            value={meta}
            onChange={setMeta}
            placeholder="Todas as Metas"
            helperText="A exportação cobre uma Meta por vez, ou todas."
            disabled={gerando}
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <Input
            type="date"
            label="Período — início"
            className="min-w-40 flex-1"
            value={inicio}
            onChange={(e) => setInicio(e.target.value)}
            disabled={gerando}
            data-testid="exportar-periodo-inicio"
          />
          <Input
            type="date"
            label="Período — fim"
            className="min-w-40 flex-1"
            value={fim}
            onChange={(e) => setFim(e.target.value)}
            disabled={gerando}
            data-testid="exportar-periodo-fim"
          />
        </div>
        <p className="text-xs leading-relaxed text-text-muted">
          Sem período informado, o arquivo traz o Plano de Trabalho inteiro.
          Ações sem datas próprias são consideradas pelo período da Meta.
        </p>

        {territorioId !== "" && (
          <p
            className="text-xs leading-relaxed text-text-muted"
            data-testid="exportar-aviso-territorio"
          >
            O filtro de território do painel também se aplica a esta exportação.
          </p>
        )}

        {/* O endpoint não aceita `status_execucao`: avisar aqui evita que o
            gestor conclua que o arquivo veio errado. */}
        {situacaoAtiva && (
          <p
            className="text-xs leading-relaxed text-text-muted"
            data-testid="exportar-aviso-situacao"
          >
            O filtro de Situação não se aplica à exportação — o arquivo traz
            todas as situações.
          </p>
        )}

        {gerando && (
          <p
            className="inline-flex items-center gap-2 text-sm text-text-muted"
            data-testid="exportar-carregando"
            role="status"
          >
            <Spinner className="h-4 w-4 animate-spin" />
            Gerando o arquivo… isso pode levar alguns segundos.
          </p>
        )}

        {erro && (
          <p
            className="rounded-md bg-error-bg px-3 py-2 text-sm text-error-text"
            data-testid="exportar-erro"
            role="alert"
          >
            {erro}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
