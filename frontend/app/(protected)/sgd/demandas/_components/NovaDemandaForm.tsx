"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { getAtividade, listAcoes } from "@/app/lib/atividades";
import {
  criarDemanda,
  STATUS_ATIVIDADE_BLOQUEIAM_DEMANDA,
  STATUS_ATIVIDADE_EXIGEM_JUSTIFICATIVA,
  type AtividadeElegivel,
  type NovaDemandaPayload,
} from "@/app/lib/demandas";
import { qk } from "@/app/lib/queryKeys";
import { fetchMunicipiosDoTerritorio, fetchTerritoryOptions } from "@/app/lib/upfs";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import { AtividadeBusca } from "./AtividadeBusca";
import { ContextoAtividade } from "./ContextoAtividade";

type Origem = "existente" | "nova";

type NovaAtividade = {
  titulo: string;
  tipo: string;
  acao: string;
  territorio: string;
  municipio: string;
  data: string;
};

const NOVA_ATIVIDADE_VAZIA: NovaAtividade = {
  titulo: "",
  tipo: "",
  acao: "",
  territorio: "",
  municipio: "",
  data: "",
};

type CampoComErro =
  | "titulo"
  | "justificativa"
  | "atividade"
  | "titulo_atividade"
  | "tipo"
  | "acao"
  | "municipio"
  | "data";
type Erros = Partial<Record<CampoComErro, string>>;

/** Campo da atividade nova → chave do erro (o título colide com o da demanda). */
const ERRO_DO_CAMPO_NOVO: Record<keyof NovaAtividade, CampoComErro | null> = {
  titulo: "titulo_atividade",
  tipo: "tipo",
  acao: "acao",
  territorio: null,
  municipio: "municipio",
  data: "data",
};

/** Campo do `DemandCreateSerializer` → campo do formulário. */
const CAMPO_DA_API: Record<string, CampoComErro> = {
  titulo: "titulo",
  justificativa: "justificativa",
  activity: "atividade",
  activity_id: "atividade",
  activity_titulo: "titulo_atividade",
  activity_tipo_atividade: "tipo",
  activity_acao_id: "acao",
  activity_municipio_id: "municipio",
  activity_data_prevista: "data",
};

type NovaDemandaFormProps = {
  /** Vindo da aba Demandas da ficha: a atividade já está decidida. */
  atividadeIdInicial: number | null;
};

/**
 * Formulário de criação de demanda (#294, SGD-RF01 a RF03).
 *
 * Três entradas, um só formulário:
 * - pela aba da atividade — contexto herdado, somente leitura;
 * - pelo SGD, escolhendo a atividade no campo com busca;
 * - pelo SGD, criando a atividade (em Planejado) com os cinco campos mínimos.
 *
 * A demanda nasce em Rascunho; a submissão é outro passo (#295/#296).
 */
export function NovaDemandaForm({ atividadeIdInicial }: NovaDemandaFormProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { data: session } = useSession();
  const choices = useSgpChoices();

  const fixa = atividadeIdInicial !== null;
  const [origem, setOrigem] = useState<Origem>("existente");
  const [escolhida, setEscolhida] = useState<AtividadeElegivel | null>(null);
  const [titulo, setTitulo] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [nova, setNova] = useState<NovaAtividade>(NOVA_ATIVIDADE_VAZIA);
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const atividadeId =
    atividadeIdInicial ?? (origem === "existente" ? (escolhida?.id ?? null) : null);

  const detalhe = useQuery({
    queryKey: qk.atividade(atividadeId ?? ""),
    queryFn: ({ signal }) => getAtividade(atividadeId!, signal),
    enabled: atividadeId !== null,
  });
  const atividade = detalhe.data ?? null;

  const criandoAtividade = !fixa && origem === "nova";

  // ── Opções da atividade nova ────────────────────────────────────────────
  const territoriosDaSessao: SelectOption[] = (session?.user?.territorios ?? []).map(
    (t) => ({ value: String(t.id), label: t.nome }),
  );
  // Super Admin não tem território na sessão (acesso global): lista todos.
  const territoriosGlobais = useQuery({
    queryKey: qk.territorios,
    queryFn: ({ signal }) => fetchTerritoryOptions(signal),
    enabled: criandoAtividade && territoriosDaSessao.length === 0,
    staleTime: Infinity,
  });
  const territorioOptions =
    territoriosDaSessao.length > 0 ? territoriosDaSessao : (territoriosGlobais.data ?? []);
  const territorioEfetivo =
    nova.territorio || (territorioOptions.length === 1 ? territorioOptions[0].value : "");

  const municipios = useQuery({
    queryKey: qk.municipiosDoTerritorio(territorioEfetivo),
    queryFn: ({ signal }) => fetchMunicipiosDoTerritorio(territorioEfetivo, signal),
    enabled: criandoAtividade && !!territorioEfetivo,
    staleTime: Infinity,
  });

  const acoes = useQuery({
    queryKey: qk.acoesPT,
    queryFn: ({ signal }) => listAcoes(signal),
    enabled: criandoAtividade,
    staleTime: Infinity,
  });
  const acaoOptions: SelectOption[] = (acoes.data ?? []).map((a) => ({
    value: String(a.id),
    label: `${a.numero} — ${a.descricao}`,
  }));

  // ── Regras vindas do status da atividade (espelham o backend) ───────────
  const bloqueada =
    atividade !== null && STATUS_ATIVIDADE_BLOQUEIAM_DEMANDA.includes(atividade.status);
  const exigeJustificativa =
    atividade !== null && STATUS_ATIVIDADE_EXIGEM_JUSTIFICATIVA.includes(atividade.status);

  function patchNova(patch: Partial<NovaAtividade>) {
    setNova((prev) => ({ ...prev, ...patch }));
    setErros((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(patch) as (keyof NovaAtividade)[]) {
        const campo = ERRO_DO_CAMPO_NOVO[k];
        if (campo) delete next[campo];
      }
      return next;
    });
  }

  function validar(): Erros {
    const e: Erros = {};
    if (!titulo.trim()) e.titulo = "Informe o título da demanda.";
    if (exigeJustificativa && !justificativa.trim()) {
      e.justificativa =
        "Obrigatória: a atividade já está em andamento ou concluída (despesa posterior).";
    }
    if (criandoAtividade) {
      if (!nova.titulo.trim()) e.titulo_atividade = "Informe o título da atividade.";
      if (!nova.tipo) e.tipo = "Escolha o tipo da atividade.";
      if (!nova.acao) e.acao = "Escolha a Ação do Plano de Trabalho.";
      if (!nova.municipio) e.municipio = "Escolha o município.";
      if (!nova.data) e.data = "Informe a data prevista.";
    } else if (atividadeId === null) {
      e.atividade = "Escolha a atividade da demanda.";
    }
    return e;
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    if (enviando || bloqueada) return;
    setErroGeral(null);
    const e = validar();
    setErros(e);
    if (Object.keys(e).length > 0) return;

    const base = { titulo: titulo.trim(), justificativa: justificativa.trim() };
    const payload: NovaDemandaPayload = criandoAtividade
      ? {
          ...base,
          atividade: {
            titulo: nova.titulo.trim(),
            tipo_atividade: nova.tipo,
            acao_id: Number(nova.acao),
            municipio_id: Number(nova.municipio),
            data_prevista: nova.data,
          },
        }
      : { ...base, atividadeId: atividadeId! };

    setEnviando(true);
    try {
      const demanda = await criarDemanda(payload);
      await queryClient.invalidateQueries({
        queryKey: qk.demandasDaAtividade(demanda.activity),
      });
      showToast(`Demanda "${demanda.titulo}" criada como rascunho.`, "success");
      router.push(`/sgp/atividades/${demanda.activity}?tab=demandas`);
    } catch (err) {
      if (err instanceof ApiError) {
        const porCampo: Erros = {};
        for (const fe of err.fieldErrors ?? []) {
          const campo = fe.field ? CAMPO_DA_API[fe.field] : undefined;
          if (campo) porCampo[campo] = fe.message;
        }
        setErros(porCampo);
        if (Object.keys(porCampo).length === 0) setErroGeral(err.message);
      } else {
        setErroGeral("Não foi possível criar a demanda. Tente novamente.");
      }
      setEnviando(false);
    }
  }

  const erroDetalhe =
    detalhe.error instanceof ApiError
      ? detalhe.error.message
      : detalhe.error
        ? "Não foi possível carregar a atividade."
        : null;

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex flex-col gap-6"
      data-testid="nova-demanda-form"
    >
      {/* ── Atividade ─────────────────────────────────────────────────── */}
      <fieldset className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6">
        <legend className="px-1 text-sm font-medium text-text">Atividade</legend>

        {!fixa && (
          <div role="radiogroup" aria-label="Origem da atividade" className="flex flex-wrap gap-4">
            {(
              [
                ["existente", "Vincular a uma atividade existente"],
                ["nova", "A atividade ainda não existe"],
              ] as const
            ).map(([valor, rotulo]) => (
              <label key={valor} className="flex cursor-pointer items-center gap-2 text-sm text-text">
                <input
                  type="radio"
                  name="origem"
                  value={valor}
                  checked={origem === valor}
                  onChange={() => {
                    setOrigem(valor);
                    setErros({});
                  }}
                  className="accent-primary"
                />
                {rotulo}
              </label>
            ))}
          </div>
        )}

        {!fixa && origem === "existente" && (
          <AtividadeBusca
            tecnicoId={String(session?.user?.id ?? "")}
            value={escolhida}
            onChange={(a) => {
              setEscolhida(a);
              setErros((prev) => ({ ...prev, atividade: undefined }));
            }}
            error={erros.atividade}
          />
        )}

        {criandoAtividade && (
          <div className="grid gap-4 sm:grid-cols-2" data-testid="nova-atividade-campos">
            <p className="text-xs text-text-muted sm:col-span-2">
              A atividade será criada em <strong>Planejado</strong>, com você como técnico
              responsável. Os demais dados podem ser completados depois, na ficha dela.
            </p>
            <div className="sm:col-span-2">
              <Input
                id="nova-atividade-titulo"
                label="Título da atividade"
                required
                value={nova.titulo}
                onChange={(e) => patchNova({ titulo: e.target.value })}
                error={erros.titulo_atividade}
              />
            </div>
            <Select
              id="nova-atividade-tipo"
              label="Tipo"
              required
              options={choices.tipo_atividade}
              value={nova.tipo}
              onChange={(v) => patchNova({ tipo: v })}
              error={erros.tipo}
            />
            <Input
              id="nova-atividade-data"
              label="Data prevista"
              type="date"
              required
              value={nova.data}
              onChange={(e) => patchNova({ data: e.target.value })}
              error={erros.data}
            />
            <div className="sm:col-span-2">
              <Select
                id="nova-atividade-acao"
                label="Ação do Plano de Trabalho"
                required
                options={acaoOptions}
                value={nova.acao}
                onChange={(v) => patchNova({ acao: v })}
                placeholder={acoes.isPending ? "Carregando…" : "Selecione..."}
                error={erros.acao}
              />
            </div>
            <Select
              id="nova-atividade-territorio"
              label="Território"
              required
              options={territorioOptions}
              value={territorioEfetivo}
              onChange={(v) => patchNova({ territorio: v, municipio: "" })}
              disabled={territorioOptions.length === 1}
            />
            <Select
              id="nova-atividade-municipio"
              label="Município"
              required
              options={municipios.data ?? []}
              value={nova.municipio}
              onChange={(v) => patchNova({ municipio: v })}
              disabled={!territorioEfetivo}
              placeholder={municipios.isFetching ? "Carregando…" : "Selecione..."}
              error={erros.municipio}
            />
          </div>
        )}

        {atividadeId !== null &&
          (detalhe.isPending ? (
            <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
              <Spinner className="h-4 w-4 animate-spin" /> Carregando a atividade…
            </p>
          ) : erroDetalhe ? (
            <p role="alert" className="text-sm text-error-text">
              {erroDetalhe}
            </p>
          ) : atividade ? (
            <ContextoAtividade atividade={atividade} />
          ) : null)}

        {bloqueada && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="demanda-atividade-bloqueada"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Atividades canceladas ou não realizadas não aceitam novas demandas.
          </p>
        )}
      </fieldset>

      {/* ── Demanda ───────────────────────────────────────────────────── */}
      <fieldset className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6">
        <legend className="px-1 text-sm font-medium text-text">Demanda</legend>
        <Input
          id="demanda-titulo"
          label="Título da demanda"
          required
          maxLength={255}
          value={titulo}
          onChange={(e) => {
            setTitulo(e.target.value);
            setErros((prev) => ({ ...prev, titulo: undefined }));
          }}
          error={erros.titulo}
        />
        <Textarea
          id="demanda-justificativa"
          label="Justificativa"
          required={exigeJustificativa}
          rows={4}
          value={justificativa}
          onChange={(e) => {
            setJustificativa(e.target.value);
            setErros((prev) => ({ ...prev, justificativa: undefined }));
          }}
          helperText={
            exigeJustificativa
              ? "Obrigatória: a atividade já está em andamento ou concluída, e a demanda fica marcada como despesa posterior."
              : "Opcional. Explique para que o recurso será usado."
          }
          error={erros.justificativa}
        />
      </fieldset>

      {erroGeral && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          data-testid="nova-demanda-erro"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {erroGeral}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={() => router.back()}>
          Cancelar
        </Button>
        <Button type="submit" loading={enviando} disabled={bloqueada} data-testid="nova-demanda-salvar">
          Criar demanda
        </Button>
      </div>
    </form>
  );
}
