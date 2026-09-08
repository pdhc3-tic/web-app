"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Layers } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useDistribuicaoScope } from "@/app/lib/auth/roles";
import { formatCurrencyBRL, moneyOrNull } from "@/app/lib/format";
import { listMetas, type MetaListItem } from "@/app/lib/metas";
import {
  atualizarAlocacao,
  criarAlocacao,
  fetchOrcamentoDaMeta,
  nivelOrcamentoLabel,
  RUBRICAS,
  valorNumerico,
  type RubricaOrcamentoApi,
} from "@/app/lib/orcamento";
import { fetchStates, fetchTerritorios, type StateItem } from "@/app/lib/upfs";
import type { Territorio } from "@/app/lib/auth/types";
import { BarraSaldo } from "./_components/BarraSaldo";
import {
  ConfirmarDistribuicaoDialog,
  type Confirmacao,
} from "./_components/ConfirmarDistribuicaoDialog";
import { DestinoLinha } from "./_components/DestinoLinha";
import {
  excedente as calcularExcedente,
  SEM_PAI,
  tetoEstadual,
  tetoTerritorial,
  type Destino,
} from "./_components/tipos";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

/**
 * Distribuição orçamentária (§5.3.2).
 *
 * A UGP distribui o nacional entre os estados; o Articulador redistribui o
 * estado dele entre os territórios. Quem faz o quê não é escolha da tela: é o
 * que `BudgetAllocationViewSet._autorizar` aceita de cada perfil — ver
 * `useDistribuicaoScope`.
 *
 * ─── O que a tela valida, e o que ela não decide ────────────────────────────
 *
 * `_checar_teto` roda no servidor dentro de uma transação, com
 * `select_for_update` no pai. A projeção daqui é espelho dela para dar resposta
 * enquanto se digita, nunca substituto: entre desenhar a barra e enviar o POST
 * cabe a distribuição de outra pessoa, e é o 400 que decide. Por isso todo erro
 * de campo do servidor é ancorado no input correspondente em vez de virar um
 * alerta genérico.
 */
export default function DistribuicaoOrcamentoPage() {
  const { loading: authLoading, pode, nivel, estados: estadosDoUsuario } =
    useDistribuicaoScope();
  const { showToast } = useToast();

  // ── Dados de apoio ────────────────────────────────────────────────────────
  const [metas, setMetas] = useState<MetaListItem[]>([]);
  const [estados, setEstados] = useState<StateItem[]>([]);
  const [territorios, setTerritorios] = useState<Territorio[]>([]);

  // ── Seleção ───────────────────────────────────────────────────────────────
  const [metaId, setMetaId] = useState("");
  const [rubricaSlug, setRubricaSlug] = useState("");
  /** Só o Articulador escolhe: é o pai de que ele redistribui. */
  const [siglaEstado, setSiglaEstado] = useState("");

  // ── Orçamento da Meta ─────────────────────────────────────────────────────
  const [orcamento, setOrcamento] = useState<RubricaOrcamentoApi[] | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erroCarga, setErroCarga] = useState<string | null>(null);
  const [recarga, setRecarga] = useState(0);

  // ── Edição ────────────────────────────────────────────────────────────────
  /** Valor digitado por destino, mascarado. Chave: id do destino. */
  const [valores, setValores] = useState<Record<number, string>>({});
  /** Erro de 400 por destino, ancorado no input. */
  const [erros, setErros] = useState<Record<number, string>>({});
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null);
  const [salvandoId, setSalvandoId] = useState<number | null>(null);

  const soUmEstado = estadosDoUsuario.length === 1;

  useEffect(() => {
    if (!pode) return;
    const controller = new AbortController();

    listMetas(controller.signal).then(setMetas).catch(() => {});

    if (nivel === "estadual") {
      fetchStates(controller.signal).then(setEstados).catch(() => {});
    } else {
      fetchTerritorios(controller.signal).then(setTerritorios).catch(() => {});
    }

    return () => controller.abort();
  }, [pode, nivel]);

  // Articulador com um estado só não precisa escolher — a tela já entra nele.
  useEffect(() => {
    if (nivel === "territorial" && soUmEstado && siglaEstado === "") {
      setSiglaEstado(estadosDoUsuario[0]);
    }
  }, [nivel, soUmEstado, siglaEstado, estadosDoUsuario]);

  // ── Carga do orçamento da Meta ────────────────────────────────────────────
  useEffect(() => {
    if (metaId === "") {
      setOrcamento(null);
      return;
    }
    const controller = new AbortController();
    setCarregando(true);
    setErroCarga(null);

    fetchOrcamentoDaMeta(Number(metaId), controller.signal)
      .then((dados) => {
        setOrcamento(dados);
        // O que estava digitado valia para outro recorte; manter o texto na
        // tela depois de trocar de Meta convidaria a gravar o valor errado.
        setValores({});
        setErros({});
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setErroCarga(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o orçamento desta Meta.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregando(false);
      });

    return () => controller.abort();
  }, [metaId, recarga]);

  const metaOptions: SelectOption[] = useMemo(
    // Mesmo contorno do painel: o backend devolve as Metas fora de ordem.
    // Ver frontend/docs/pendencias-backend-sprint-9.md, item 8.
    () =>
      [...metas]
        .sort((a, b) => a.numero - b.numero)
        .map((m) => ({
          value: String(m.id),
          label: `Meta ${m.numero} – ${m.titulo}`,
        })),
    [metas],
  );

  const rubricaOptions: SelectOption[] = useMemo(
    () => RUBRICAS.map((r) => ({ value: r.slug, label: r.nome })),
    [],
  );

  /** Só os estados do Articulador — o backend recusaria qualquer outro. */
  const estadosDoArticulador: SelectOption[] = useMemo(
    () => estadosDoUsuario.map((s) => ({ value: s, label: s })),
    [estadosDoUsuario],
  );

  const estadosPorTerritorio = useMemo(
    () => new Map(territorios.map((t) => [t.id, t.estados ?? []])),
    [territorios],
  );

  const rubricaAtual = useMemo(
    () => orcamento?.find((r) => r.rubrica.slug === rubricaSlug) ?? null,
    [orcamento, rubricaSlug],
  );

  // ── Destinos ──────────────────────────────────────────────────────────────
  const destinos: Destino[] = useMemo(() => {
    if (!rubricaAtual) return [];

    if (nivel === "estadual") {
      // `id` é a PK do State, que é o que `estado_id` do payload exige; o
      // casamento com o que já existe é por SIGLA, que é como o detalhamento
      // identifica o estado.
      return [...estados]
        .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"))
        .map((e) => ({
          id: e.id,
          nome: `${e.nome} (${e.sigla})`,
          alocacao:
            rubricaAtual.detalhamento.find(
              (a) => a.nivel === "estadual" && a.estado?.sigla === e.sigla,
            ) ?? null,
        }));
    }

    if (siglaEstado === "") return [];
    return territorios
      .filter((t) => (t.estados ?? []).includes(siglaEstado))
      .map((t) => ({
        id: t.id,
        nome: t.nome,
        alocacao:
          rubricaAtual.detalhamento.find(
            (a) => a.nivel === "territorial" && a.territorio?.id === t.id,
          ) ?? null,
      }));
  }, [rubricaAtual, nivel, estados, territorios, siglaEstado]);

  const teto = useMemo(() => {
    if (!rubricaAtual) return null;
    return nivel === "estadual"
      ? tetoEstadual(rubricaAtual)
      : siglaEstado === ""
        ? null
        : tetoTerritorial(rubricaAtual, siglaEstado, estadosPorTerritorio);
  }, [rubricaAtual, nivel, siglaEstado, estadosPorTerritorio]);

  const tetoResolvido = teto !== null && teto !== SEM_PAI ? teto : null;

  /** Soma dos gravados com o texto em edição substituindo o próprio destino. */
  const projetado = useMemo(() => {
    if (!tetoResolvido) return 0;
    return destinos.reduce((soma, d) => {
      const digitado = valores[d.id];
      const gravado = d.alocacao ? valorNumerico(d.alocacao.valor_alocado) : 0;
      if (digitado === undefined || digitado.trim() === "") return soma + gravado;
      return soma + Number(moneyOrNull(digitado) ?? "0");
    }, 0);
  }, [destinos, valores, tetoResolvido]);

  const excedentePorDestino = useMemo(() => {
    const mapa: Record<number, number> = {};
    if (!tetoResolvido) return mapa;
    for (const d of destinos) {
      const digitado = valores[d.id];
      if (digitado === undefined || digitado.trim() === "") continue;
      mapa[d.id] = calcularExcedente(
        tetoResolvido,
        d,
        Number(moneyOrNull(digitado) ?? "0"),
      );
    }
    return mapa;
  }, [destinos, valores, tetoResolvido]);

  const excedenteMaximo = Math.max(0, ...Object.values(excedentePorDestino), 0);

  // ── Gravação ──────────────────────────────────────────────────────────────
  const abrirConfirmacao = useCallback(
    (destino: Destino) => {
      const digitado = valores[destino.id] ?? "";
      const valor = moneyOrNull(digitado);
      if (valor === null || !rubricaAtual) return;

      setConfirmacao({
        destino,
        valor,
        metaLabel:
          metaOptions.find((m) => m.value === metaId)?.label ?? `Meta ${metaId}`,
        rubricaLabel: rubricaAtual.rubrica.nome,
        nivelLabel: nivelOrcamentoLabel(nivel === "estadual" ? "estadual" : "territorial"),
      });
    },
    [valores, rubricaAtual, metaOptions, metaId, nivel],
  );

  const confirmar = useCallback(async () => {
    if (!confirmacao || !rubricaAtual) return;
    const { destino, valor } = confirmacao;
    const destinoId = destino.id;

    setSalvandoId(destinoId);
    setErros((e) => ({ ...e, [destinoId]: "" }));

    try {
      if (destino.alocacao) {
        await atualizarAlocacao(destino.alocacao.id, valor);
      } else {
        await criarAlocacao(Number(metaId), {
          rubrica_id: rubricaAtual.rubrica.id,
          nivel: nivel === "estadual" ? "estadual" : "territorial",
          ...(nivel === "estadual"
            ? { estado_id: destinoId }
            : { territorio_id: destinoId }),
          valor_alocado: valor,
        });
      }

      setConfirmacao(null);
      setValores((v) => {
        const proximo = { ...v };
        delete proximo[destinoId];
        return proximo;
      });
      showToast(
        `${destino.nome}: ${formatCurrencyBRL(valor)} ${
          destino.alocacao ? "ajustado" : "distribuído"
        }.`,
        "success",
      );
      // Recarrega o orçamento em vez de remendar o estado local: os agregados
      // do pai também mudaram, e recalcular a barra a partir da resposta de uma
      // alocação só reproduziria a conta do servidor pela metade.
      setRecarga((r) => r + 1);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        // Todo erro de teto e de piso vem em `valor_alocado`; `nivel` é o do
        // pai ausente. Os dois pertencem a este destino, e é nele que ficam.
        const msg = e.fieldErrors.map((fe) => fe.message).join(" ");
        setErros((err) => ({ ...err, [destinoId]: msg }));
      } else {
        setErros((err) => ({
          ...err,
          [destinoId]:
            e instanceof ApiError
              ? e.message
              : "Não foi possível gravar. Tente novamente.",
        }));
      }
      setConfirmacao(null);
    } finally {
      setSalvandoId(null);
    }
  }, [confirmacao, rubricaAtual, metaId, nivel, showToast]);

  // ── Render ────────────────────────────────────────────────────────────────
  if (authLoading) return <CenteredSpinner />;

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Distribuição orçamentária
      </h1>
    </PageHeader>
  );

  if (!pode) {
    return (
      <>
        {header}
        <RestrictedAccess
          title="Distribuição restrita"
          description="Apenas a UGP, o Super Admin e o Articulador Estadual distribuem orçamento. Você pode acompanhar os valores no Painel de Orçamento."
        />
      </>
    );
  }

  const origem =
    nivel === "estadual" ? "nível nacional" : `alocação estadual de ${siglaEstado}`;

  const precisaEscolherEstado = nivel === "territorial" && siglaEstado === "";
  const pronto = metaId !== "" && rubricaSlug !== "" && !precisaEscolherEstado;

  return (
    <div data-testid="distribuicao-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Orçamento", href: "/sgp/orcamento" },
            { label: "Distribuição" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          {nivel === "estadual"
            ? "Distribua o valor aprovado de cada rubrica entre os estados. O teto é o saldo do nível nacional, e cada gravação fica registrada com uma transação em seu nome."
            : "Redistribua entre os territórios o que o seu estado recebeu. O teto é o saldo da alocação estadual, e cada gravação fica registrada com uma transação em seu nome."}
        </p>

        {/* Escolha do recorte */}
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4">
          <div className="min-w-56 flex-1">
            <Select
              id="distribuicao-meta"
              label="Meta"
              options={[{ value: "", label: "Selecione a Meta" }, ...metaOptions]}
              value={metaId}
              onChange={setMetaId}
              placeholder="Selecione a Meta"
            />
          </div>

          <div className="min-w-44 flex-1">
            <Select
              id="distribuicao-rubrica"
              label="Rubrica"
              options={[
                { value: "", label: "Selecione a rubrica" },
                ...rubricaOptions,
              ]}
              value={rubricaSlug}
              onChange={setRubricaSlug}
              placeholder="Selecione a rubrica"
            />
          </div>

          {/* Só o Articulador: é o pai de que ele redistribui, e a lista tem
              apenas os estados dele — `_autorizar` recusaria qualquer outro. */}
          {nivel === "territorial" && (
            <div className="min-w-40 flex-1">
              <Select
                id="distribuicao-estado"
                label="Estado"
                options={[
                  { value: "", label: "Selecione o estado" },
                  ...estadosDoArticulador,
                ]}
                value={siglaEstado}
                onChange={setSiglaEstado}
                placeholder="Selecione o estado"
              />
            </div>
          )}
        </div>

        {erroCarga ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{erroCarga}</p>
            <Button variant="secondary" onClick={() => setRecarga((r) => r + 1)}>
              Tentar novamente
            </Button>
          </div>
        ) : !pronto ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Layers className="h-7 w-7" />}
              title="Escolha o que distribuir"
              description={
                precisaEscolherEstado && metaId !== "" && rubricaSlug !== ""
                  ? "Selecione o estado de onde o valor será redistribuído."
                  : "Selecione a Meta e a rubrica para ver o saldo disponível e os destinos."
              }
            />
          </div>
        ) : carregando && orcamento === null ? (
          <CenteredSpinner />
        ) : teto === SEM_PAI ? (
          <div
            className="rounded-lg border border-border bg-surface"
            data-testid="distribuicao-sem-pai"
          >
            <EmptyState
              icon={<AlertTriangle className="h-7 w-7" />}
              title="O nível acima ainda não foi distribuído"
              description={
                nivel === "estadual"
                  ? "Esta rubrica não tem valor aprovado no nível nacional para esta Meta. Sem a linha nacional não há teto contra o qual distribuir."
                  : `Não há alocação estadual de ${siglaEstado} nesta rubrica. A UGP precisa distribuir para o seu estado antes que você possa repassar aos territórios.`
              }
            />
          </div>
        ) : tetoResolvido ? (
          <div
            aria-busy={carregando}
            className={`flex flex-col gap-4 transition-opacity ${
              carregando ? "opacity-60" : ""
            }`}
          >
            <BarraSaldo
              teto={tetoResolvido}
              projetado={projetado}
              excedente={excedenteMaximo}
              origem={origem}
            />

            {destinos.length === 0 ? (
              <div className="rounded-lg border border-border bg-surface">
                <EmptyState
                  icon={<Layers className="h-7 w-7" />}
                  title="Nenhum destino disponível"
                  description="Não há territórios cadastrados para este estado."
                />
              </div>
            ) : (
              <ul
                className="rounded-lg border border-border bg-surface"
                data-testid="distribuicao-destinos"
              >
                {destinos.map((destino) => (
                  <DestinoLinha
                    key={destino.id}
                    destino={destino}
                    valor={valores[destino.id] ?? ""}
                    onChange={(v) =>
                      setValores((atual) => ({ ...atual, [destino.id]: v }))
                    }
                    onDistribuir={() => abrirConfirmacao(destino)}
                    excedente={excedentePorDestino[destino.id] ?? 0}
                    erro={erros[destino.id] || undefined}
                    salvando={salvandoId === destino.id}
                    desabilitado={
                      salvandoId !== null && salvandoId !== destino.id
                    }
                  />
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>

      <ConfirmarDistribuicaoDialog
        confirmacao={confirmacao}
        onCancel={() => setConfirmacao(null)}
        onConfirm={confirmar}
        salvando={salvandoId !== null}
      />
    </div>
  );
}
