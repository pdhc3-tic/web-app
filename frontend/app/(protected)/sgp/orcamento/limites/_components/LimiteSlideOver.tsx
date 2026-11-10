"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import {
  SearchSelect,
  type SearchSelectOption,
} from "@/app/components/ui/SearchSelect/SearchSelect";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { fetchOpcoesUsuarios } from "@/app/lib/execucaoSgd";
import { formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import {
  alterarLimite,
  criarLimite,
  sobrealocacaoDoErro,
  type LimiteGasto,
  type PerfilOperacional,
  type Sobrealocacao,
} from "@/app/lib/limites";
import { qk } from "@/app/lib/queryKeys";
import type { Rubrica } from "@/app/lib/tiposSolicitacao";
import { PrecedenciaSelo } from "./PrecedenciaSelo";

/** O que está sendo editado — decide os campos, a rota e a obrigatoriedade da justificativa. */
export type Edicao =
  | { tipo: "padrao-novo"; perfil: PerfilOperacional; rubrica: Rubrica }
  | { tipo: "padrao-alterar"; perfil: PerfilOperacional; limite: LimiteGasto }
  | { tipo: "sobrescrita-nova" }
  | { tipo: "sobrescrita-alterar"; limite: LimiteGasto };

type Props = {
  edicao: Edicao | null;
  rubricas: Rubrica[];
  onClose: () => void;
  onSalvo: (limite: LimiteGasto, edicao: Edicao) => void;
};

type Erros = Partial<Record<"user" | "rubrica" | "valor" | "justificativa", string>>;

const CAMPO_DA_API: Record<string, keyof Erros> = {
  user: "user",
  rubrica: "rubrica",
  valor_limite: "valor",
  justificativa: "justificativa",
};

function titulo(e: Edicao): string {
  switch (e.tipo) {
    case "padrao-novo":
      return `Padrão de ${e.perfil.nome} — ${e.rubrica.nome}`;
    case "padrao-alterar":
      return `Padrão de ${e.perfil.nome} — ${e.limite.rubrica_nome}`;
    case "sobrescrita-nova":
      return "Nova sobrescrita individual";
    case "sobrescrita-alterar":
      return `${e.limite.user_nome ?? "Limite individual"} — ${e.limite.rubrica_nome}`;
  }
}

/** A justificativa só é opcional ao criar um padrão (o backend aceita vazia). */
const justificativaObrigatoria = (e: Edicao) => e.tipo !== "padrao-novo";

/**
 * Criar ou alterar um limite (#400): padrão do perfil ou sobrescrita
 * individual. O backend decide período, teto e precedência; a tela só manda o
 * valor e a justificativa e mostra o que ele responde — inclusive a
 * sobrealocação, com a soma dos limites e o pool.
 */
export function LimiteSlideOver({ edicao, ...resto }: Props) {
  // Montado só enquanto há algo em edição: cada abertura começa do zero, sem
  // resto da anterior.
  if (!edicao) return null;
  return <FormularioLimite edicao={edicao} {...resto} />;
}

/** O valor atual da linha em edição, já mascarado; vazio ao criar. */
function valorInicial(edicao: Edicao): string {
  if (edicao.tipo === "padrao-alterar" || edicao.tipo === "sobrescrita-alterar") {
    return formatMoneyInput(Number(edicao.limite.valor_limite).toFixed(2));
  }
  return "";
}

function FormularioLimite({ edicao, rubricas, onClose, onSalvo }: Props & { edicao: Edicao }) {
  const [usuario, setUsuario] = useState<SearchSelectOption<number> | null>(null);
  const [rubricaId, setRubricaId] = useState("");
  const [valor, setValor] = useState(() => valorInicial(edicao));
  const [justificativa, setJustificativa] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [sobrealocacao, setSobrealocacao] = useState<Sobrealocacao | null>(null);
  const [salvando, setSalvando] = useState(false);

  const nova = edicao.tipo === "sobrescrita-nova";
  const usuarios = useQuery({
    queryKey: qk.execucao.opcoesUsuarios("solicitante"),
    queryFn: ({ signal }) => fetchOpcoesUsuarios("solicitante", signal),
    enabled: nova,
    staleTime: 5 * 60_000,
  });

  const limiteAtual =
    edicao.tipo === "padrao-alterar" || edicao.tipo === "sobrescrita-alterar" ? edicao.limite : null;
  const obrigatoria = justificativaObrigatoria(edicao);

  function validar(): Erros {
    const e: Erros = {};
    if (nova && !usuario) e.user = "Escolha a pessoa.";
    if (nova && !rubricaId) e.rubrica = "Escolha a rubrica.";
    if (moneyOrNull(valor) === null) e.valor = "Informe o valor do limite.";
    if (obrigatoria && !justificativa.trim()) e.justificativa = "Obrigatória: registre o motivo do limite.";
    return e;
  }

  async function salvar() {
    if (salvando) return;
    setErroGeral(null);
    setSobrealocacao(null);
    const e = validar();
    setErros(e);
    if (Object.keys(e).length > 0) return;

    const valorLimite = moneyOrNull(valor)!;
    const just = justificativa.trim();
    setSalvando(true);
    try {
      let salvo: LimiteGasto;
      if (edicao.tipo === "padrao-novo") {
        salvo = await criarLimite({
          escopo: "perfil", perfil: edicao.perfil.id, rubrica: edicao.rubrica.id,
          valor_limite: valorLimite, justificativa: just,
        });
      } else if (edicao.tipo === "sobrescrita-nova") {
        salvo = await criarLimite({
          escopo: "individual", user: usuario!.item, rubrica: Number(rubricaId),
          valor_limite: valorLimite, justificativa: just,
        });
      } else {
        salvo = await alterarLimite(edicao.limite.id, { valor_limite: valorLimite, justificativa: just });
      }
      onSalvo(salvo, edicao);
    } catch (err) {
      const excesso = sobrealocacaoDoErro(err);
      if (excesso) {
        setSobrealocacao(excesso);
      } else if (err instanceof ApiError) {
        const porCampo: Erros = {};
        let semCampo: string | null = null;
        for (const fe of err.fieldErrors ?? []) {
          const campo = fe.field ? CAMPO_DA_API[fe.field] : undefined;
          // Usuário e rubrica só têm campo na sobrescrita nova; nas outras, o
          // conflito ("já existe…") vai para o aviso geral.
          if (campo && (nova || (campo !== "user" && campo !== "rubrica"))) porCampo[campo] = fe.message;
          else semCampo ??= fe.message;
        }
        setErros(porCampo);
        if (semCampo || Object.keys(porCampo).length === 0) setErroGeral(semCampo ?? err.message);
      } else {
        setErroGeral("Não foi possível salvar o limite. Tente novamente.");
      }
    } finally {
      setSalvando(false);
    }
  }

  const opcoesUsuarios = (usuarios.data ?? []).map((o) => ({
    value: o.value,
    label: o.label,
    item: Number(o.value),
  }));

  return (
    <SlideOver
      open
      onClose={onClose}
      title={titulo(edicao)}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={() => void salvar()} loading={salvando} data-testid="limite-salvar">
            Salvar
          </Button>
        </div>
      }
    >
      <form
        className="flex flex-col gap-4 px-4 py-4"
        noValidate
        onSubmit={(ev) => {
          ev.preventDefault();
          void salvar();
        }}
        data-testid="limite-form"
      >
        {limiteAtual && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
            <PrecedenciaSelo limite={limiteAtual} />
            <span className="tabular-nums">Atual: {formatCurrencyBRL(limiteAtual.valor_limite)}</span>
          </div>
        )}

        {edicao.tipo === "padrao-alterar" && (
          <p className="text-xs text-text-muted">
            Se alguém do perfil já usou este padrão no período, o valor novo vale a partir do
            próximo período; quem já tem a linha deste período fica como está.
          </p>
        )}
        {edicao.tipo === "sobrescrita-alterar" && (
          <p className="text-xs text-text-muted">
            Reduzir não desfaz o que já foi autorizado: o novo teto vale para as próximas reservas.
          </p>
        )}

        {nova && (
          <>
            <SearchSelect<number>
              label="Pessoa"
              required
              value={usuario}
              onChange={(o) => {
                setUsuario(o);
                setErros((p) => ({ ...p, user: undefined }));
              }}
              // A lista já vem inteira (os ADTs ativos); a busca filtra aqui.
              search={async (texto) => {
                const t = texto.trim().toLowerCase();
                return t ? opcoesUsuarios.filter((o) => o.label.toLowerCase().includes(t)) : opcoesUsuarios;
              }}
              queryKey={(texto) => ["limites", "usuarios", texto, opcoesUsuarios.length]}
              placeholder={usuarios.isPending ? "Carregando…" : "Buscar pelo nome…"}
              emptyText="Nenhuma pessoa encontrada."
              error={erros.user}
              data-testid="limite-usuario"
            />
            <Select
              id="limite-rubrica"
              label="Rubrica"
              required
              options={rubricas.map((r) => ({ value: String(r.id), label: r.nome }))}
              value={rubricaId}
              onChange={(v) => {
                setRubricaId(v);
                setErros((p) => ({ ...p, rubrica: undefined }));
              }}
              error={erros.rubrica}
            />
          </>
        )}

        <Input
          id="limite-valor"
          label="Valor do limite"
          required
          inputMode="numeric"
          placeholder="R$ 0,00"
          value={valor}
          onChange={(e) => {
            setValor(formatMoneyInput(e.target.value));
            setErros((p) => ({ ...p, valor: undefined }));
            setSobrealocacao(null);
          }}
          error={erros.valor}
          data-testid="limite-valor"
        />

        <Textarea
          id="limite-justificativa"
          label="Justificativa"
          required={obrigatoria}
          rows={3}
          value={justificativa}
          onChange={(e) => {
            setJustificativa(e.target.value);
            setErros((p) => ({ ...p, justificativa: undefined }));
          }}
          helperText={
            obrigatoria
              ? "Obrigatória: fica registrada no histórico do limite."
              : "Opcional ao criar o padrão."
          }
          error={erros.justificativa}
          data-testid="limite-justificativa"
        />

        {sobrealocacao && (
          <div
            role="alert"
            className="flex flex-col gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="limite-sobrealocacao"
          >
            <p className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              A soma dos limites do território passaria do pool, e a sobrealocação está desligada.
            </p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 pl-6 tabular-nums">
              <dt>Soma dos limites</dt>
              <dd className="font-semibold" data-testid="limite-sobrealocacao-soma">
                {formatCurrencyBRL(sobrealocacao.somaLimites)}
              </dd>
              <dt>Pool do território</dt>
              <dd className="font-semibold" data-testid="limite-sobrealocacao-pool">
                {formatCurrencyBRL(sobrealocacao.valorPool)}
              </dd>
            </dl>
          </div>
        )}

        {erroGeral && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="limite-erro"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {erroGeral}
          </p>
        )}
      </form>
    </SlideOver>
  );
}
