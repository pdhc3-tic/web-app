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
import {
  atualizarPool,
  criarPool,
  fetchPainelOrcamento,
  nivelOrcamentoLabel,
  RUBRICAS,
  type PoolOrcamentoApi,
} from "@/app/lib/orcamento";
import { fetchStates, fetchTerritorios, type StateItem } from "@/app/lib/ufpas";
import type { Territorio } from "@/app/lib/auth/types";
import { BarraSaldo } from "./_components/BarraSaldo";
import {
  ConfirmarDistribuicaoDialog,
  type Confirmacao,
} from "./_components/ConfirmarDistribuicaoDialog";
import { DestinoLinha } from "./_components/DestinoLinha";
import {
  projetar,
  SEM_PAI,
  tetoDoPool,
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
 * Distribuição orçamentária (§5.3.2), sobre o orçamento por pool (#398).
 *
 * A UGP distribui o pool nacional de uma rubrica entre os estados; o
 * Articulador redistribui o pool do estado dele entre os territórios. Sem Meta:
 * desde a #384 o saldo é do pool. Quem faz o quê é o que
 * `BudgetPoolViewSet._autorizar` aceita de cada perfil — ver
 * `useDistribuicaoScope`.
 *
 * ─── O que a tela valida, e o que ela não decide ────────────────────────────
 *
 * O teto roda no servidor dentro de uma transação, com
 * `select_for_update` no pool de cima. A projeção daqui é espelho dela para dar resposta
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
  const [estados, setEstados] = useState<StateItem[]>([]);
  const [territorios, setTerritorios] = useState<Territorio[]>([]);

  // ── Seleção ───────────────────────────────────────────────────────────────
  const [rubricaSlug, setRubricaSlug] = useState("");
  /** Só o Articulador escolhe: é o pai de que ele redistribui. */
  const [siglaEstado, setSiglaEstado] = useState("");

  // ── Pools da rubrica ──────────────────────────────────────────────────────
  /** O pool de cima e os de baixo já gravados, do painel por rubrica (e estado). */
  const [pools, setPools] = useState<PoolOrcamentoApi[] | null>(null);
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

  // ── Carga dos pools da rubrica ────────────────────────────────────────────
  // A UGP lê a rubrica inteira (o nacional e os estaduais); o Articulador desce
  // ao estado escolhido (o pool do estado e os dos territórios dele).
  const precisaEstado = nivel === "territorial";
  useEffect(() => {
    if (rubricaSlug === "" || (precisaEstado && siglaEstado === "")) {
      setPools(null);
      return;
    }
    const controller = new AbortController();
    setCarregando(true);
    setErroCarga(null);

    fetchPainelOrcamento(
      precisaEstado ? { rubrica: rubricaSlug, estado: siglaEstado } : { rubrica: rubricaSlug },
      controller.signal,
    )
      .then((dados) => {
        setPools(dados);
        // O que estava digitado valia para outro recorte; manter o texto na
        // tela depois de trocar de rubrica convidaria a gravar o valor errado.
        setValores({});
        setErros({});
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setErroCarga(e instanceof ApiError ? e.message : "Não foi possível carregar o orçamento desta rubrica.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregando(false);
      });

    return () => controller.abort();
  }, [rubricaSlug, siglaEstado, precisaEstado, recarga]);

  const rubricaOptions: SelectOption[] = useMemo(
    () => RUBRICAS.map((r) => ({ value: r.slug, label: r.nome })),
    [],
  );

  /** Só os estados do Articulador — o backend recusaria qualquer outro. */
  const estadosDoArticulador: SelectOption[] = useMemo(
    () => estadosDoUsuario.map((s) => ({ value: s, label: s })),
    [estadosDoUsuario],
  );

  /** O pool de onde sai o valor: o nacional (UGP) ou o do estado escolhido (Articulador). */
  const pai = useMemo(() => {
    if (!pools) return null;
    return nivel === "estadual"
      ? (pools.find((p) => p.nivel === "nacional" && !p.reserva_ugp) ?? null)
      : (pools.find((p) => p.nivel === "estadual" && p.estado?.sigla === siglaEstado) ?? null);
  }, [pools, nivel, siglaEstado]);

  const rubricaAtual = useMemo(() => RUBRICAS.find((r) => r.slug === rubricaSlug) ?? null, [rubricaSlug]);

  // ── Destinos ──────────────────────────────────────────────────────────────
  const destinos: Destino[] = useMemo(() => {
    if (!pools) return [];

    if (nivel === "estadual") {
      // `id` é a PK do State, que é o que `estado_id` do payload exige; o
      // casamento com o pool que já existe é pela sigla.
      return [...estados]
        .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"))
        .map((e) => ({
          id: e.id,
          nome: `${e.nome} (${e.sigla})`,
          pool: pools.find((p) => p.nivel === "estadual" && p.estado?.sigla === e.sigla) ?? null,
        }));
    }

    if (siglaEstado === "") return [];
    return territorios
      .filter((t) => (t.estados ?? []).includes(siglaEstado))
      .map((t) => ({
        id: t.id,
        nome: t.nome,
        pool: pools.find((p) => p.nivel === "territorial" && p.territorio?.id === t.id) ?? null,
      }));
  }, [pools, nivel, estados, territorios, siglaEstado]);

  const teto = useMemo(() => (pools ? tetoDoPool(pai) : null), [pools, pai]);

  const tetoResolvido = teto !== null && teto !== SEM_PAI ? teto : null;

  /** Os rascunhos já em número; ausente = linha intocada. */
  const rascunhos = useMemo(() => {
    const mapa: Record<number, number | undefined> = {};
    for (const d of destinos) {
      const digitado = valores[d.id];
      if (digitado === undefined || digitado.trim() === "") continue;
      mapa[d.id] = Number(moneyOrNull(digitado) ?? "0");
    }
    return mapa;
  }, [destinos, valores]);

  /**
   * Uma projeção só para a barra e para as linhas.
   *
   * O bloqueio é do CONJUNTO, não de cada linha isolada: com dois destinos em
   * edição, dois valores que cabem sozinhos podem estourar somados. Enquanto o
   * excedente era calculado destino a destino, a barra desenhava o total acima
   * do teto e os dois botões continuavam habilitados — a tela contradizia a si
   * mesma na mesma renderização.
   */
  const projecao = useMemo(
    () =>
      tetoResolvido
        ? projetar(tetoResolvido, destinos, rascunhos)
        : {
            total: 0,
            excedenteConjunto: 0,
            excedentePorDestino: {} as Record<number, number>,
            emEdicao: [] as number[],
          },
    [tetoResolvido, destinos, rascunhos],
  );

  // ── Gravação ──────────────────────────────────────────────────────────────
  const abrirConfirmacao = useCallback(
    (destino: Destino) => {
      const digitado = valores[destino.id] ?? "";
      const valor = moneyOrNull(digitado);
      if (valor === null || !rubricaAtual) return;

      setConfirmacao({
        destino,
        valor,
        rubricaLabel: rubricaAtual.nome,
        nivelLabel: nivelOrcamentoLabel(nivel === "estadual" ? "estadual" : "territorial"),
      });
    },
    [valores, rubricaAtual, nivel],
  );

  const confirmar = useCallback(async () => {
    if (!confirmacao || !pai) return;
    const { destino, valor } = confirmacao;
    const destinoId = destino.id;

    setSalvandoId(destinoId);
    setErros((e) => ({ ...e, [destinoId]: "" }));

    try {
      if (destino.pool) {
        await atualizarPool(destino.pool.id, valor);
      } else {
        await criarPool({
          rubrica_id: pai.rubrica.id,
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
          destino.pool ? "ajustado" : "distribuído"
        }.`,
        "success",
      );
      // Recarrega os pools em vez de remendar o estado local: os agregados do
      // pai também mudaram, e recalcular a barra a partir da resposta de um
      // pool só reproduziria a conta do servidor pela metade.
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
  }, [confirmacao, pai, nivel, showToast]);

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
    nivel === "estadual" ? "pool nacional" : `pool estadual de ${siglaEstado}`;

  const precisaEscolherEstado = nivel === "territorial" && siglaEstado === "";
  const pronto = rubricaSlug !== "" && !precisaEscolherEstado;

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
            ? "Distribua o pool nacional de cada rubrica entre os estados. O teto é o saldo do pool nacional, e cada gravação fica registrada em seu nome."
            : "Redistribua entre os territórios o que o pool do seu estado recebeu. O teto é o saldo do pool estadual, e cada gravação fica registrada em seu nome."}
        </p>

        {/* Escolha do recorte */}
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4">
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
                precisaEscolherEstado && rubricaSlug !== ""
                  ? "Selecione o estado de onde o valor será redistribuído."
                  : "Selecione a rubrica para ver o saldo disponível e os destinos."
              }
            />
          </div>
        ) : carregando && pools === null ? (
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
                  ? "Esta rubrica não tem pool nacional com valor aprovado. Sem ele não há teto contra o qual distribuir."
                  : `Não há pool estadual de ${siglaEstado} nesta rubrica. A UGP precisa distribuir para o seu estado antes que você possa repassar aos territórios.`
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
              projetado={projecao.total}
              excedente={projecao.excedenteConjunto}
              emEdicao={projecao.emEdicao.length}
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
                    excedente={
                      projecao.excedentePorDestino[destino.id] ?? 0
                    }
                    excedenteConjunto={projecao.excedenteConjunto}
                    destinosEmEdicao={projecao.emEdicao.length}
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
