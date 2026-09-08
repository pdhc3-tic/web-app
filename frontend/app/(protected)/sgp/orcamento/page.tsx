"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { AlertTriangle, Wallet } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { canDistribuirOrcamento, useOrcamentoScope } from "@/app/lib/auth/roles";
import { listMetas, type MetaListItem } from "@/app/lib/metas";
import {
  fetchPainelOrcamento,
  linhaVazia,
  nivelDaLinha,
  percentualComprometido,
  RUBRICAS,
  RUBRICA_SLUGS,
  type NivelOrcamento,
  type PainelOrcamentoLinhaApi,
} from "@/app/lib/orcamento";
import { fetchStateSiglaOptions, fetchTerritoryMap } from "@/app/lib/upfs";
import { AlertaAlocacoesCriticas } from "./_components/AlertaAlocacoesCriticas";
import { CelulaDetalheSlideOver } from "./_components/CelulaDetalheSlideOver";
import { MatrizOrcamento } from "./_components/MatrizOrcamento";
import { MatrizSkeleton } from "./_components/MatrizSkeleton";
import { BudgetBalance } from "@/app/components/sgp/BudgetBalance/BudgetBalance";
import {
  FILTROS_VAZIOS,
  OrcamentoFilters,
  type OrcamentoFiltersValue,
} from "./_components/OrcamentoFilters";
import type {
  CelulaOrcamento,
  EscopoExibido,
  MetaComRubricas,
} from "./_components/tipos";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function PainelOrcamentoConteudo() {
  const { data: session } = useSession();
  const { loading: authLoading, soTerritorio } = useOrcamentoScope();
  const podeDistribuir = canDistribuirOrcamento(session?.user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Dados de apoio dos selects, carregados uma única vez.
  const [metas, setMetas] = useState<MetaListItem[]>([]);
  const [estados, setEstados] = useState<SelectOption[]>([]);
  const [territorios, setTerritorios] = useState<SelectOption[]>([]);

  const [linhas, setLinhas] = useState<PainelOrcamentoLinhaApi[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [selecionada, setSelecionada] = useState<CelulaOrcamento | null>(null);

  // ── Filtros: a URL é o estado ─────────────────────────────────────────────
  // Compartilhar o recorte por link e sobreviver a refresh/voltar sai de graça
  // quando não há cópia local para sincronizar. Mesma decisão do painel do PT.
  //
  // Os valores são saneados na leitura: a URL é digitável, e o backend responde
  // 400 a um id não numérico. Ignorar o que não pode ser um filtro degrada para
  // "sem filtro" em vez de trocar o painel por uma tela de erro.
  const filtros: OrcamentoFiltersValue = useMemo(() => {
    const id = (chave: string) => {
      const bruto = searchParams.get(chave) ?? "";
      return /^\d+$/.test(bruto) ? bruto : "";
    };
    // Rubrica é slug e estado é sigla. A rubrica é conferida contra o catálogo
    // (§5.3.1); a sigla, só pela forma — quais existem é o backend que sabe, e
    // ele responde 400 a uma inexistente.
    const slug = searchParams.get("rubrica") ?? "";
    const sigla = (searchParams.get("estado") ?? "").toUpperCase();

    return {
      meta: id("meta"),
      rubrica: RUBRICA_SLUGS.includes(slug) ? slug : "",
      // ADT/ACR recebe 403 se mandar `estado`. Descartar na leitura impede que
      // uma URL colada de outro perfil quebre a tela dele.
      estado: !soTerritorio && /^[A-Z]{2}$/.test(sigla) ? sigla : "",
      territorio: soTerritorio ? "" : id("territorio"),
    };
  }, [searchParams, soTerritorio]);

  const escreverFiltros = useCallback(
    (proximos: OrcamentoFiltersValue) => {
      const qs = new URLSearchParams();
      for (const [chave, valor] of Object.entries(proximos)) {
        if (valor) qs.set(chave, valor);
      }
      const query = qs.toString();
      // `replace` e não `push`: mexer num Select não é navegação, e empilhar
      // uma entrada por tecla obrigaria o usuário a voltar N vezes.
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [router, pathname],
  );

  const patchFiltros = useCallback(
    (patch: Partial<OrcamentoFiltersValue>) =>
      escreverFiltros({ ...filtros, ...patch }),
    [escreverFiltros, filtros],
  );

  const limparFiltros = useCallback(
    () => escreverFiltros(FILTROS_VAZIOS),
    [escreverFiltros],
  );

  // ── Dados de apoio (uma vez) ──────────────────────────────────────────────
  // Só alimentam selects: uma falha aqui deixa um filtro vazio, não derruba a
  // matriz. Por isso os catches são silenciosos — o erro que importa é o do
  // painel, tratado no efeito abaixo.
  useEffect(() => {
    const controller = new AbortController();

    listMetas(controller.signal).then(setMetas).catch(() => {});

    // O ADT não tem esses dois selects; poupar as chamadas evita dois 200
    // inúteis a cada abertura da tela.
    if (!soTerritorio) {
      // Sigla, não id: `BudgetPainelQuerySerializer` valida `estado` por sigla.
      fetchStateSiglaOptions(controller.signal).then(setEstados).catch(() => {});

      fetchTerritoryMap(controller.signal)
        .then((mapa) => {
          setTerritorios(
            [...mapa.entries()]
              .map(([id, nome]) => ({ value: String(id), label: nome }))
              .sort((a, b) => a.label.localeCompare(b.label, "pt-BR")),
          );
        })
        .catch(() => {});
    }

    return () => controller.abort();
  }, [soTerritorio]);

  // ── Matriz (refeita a cada filtro) ────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    fetchPainelOrcamento(
      {
        meta: filtros.meta,
        rubrica: filtros.rubrica,
        estado: filtros.estado,
        territorio: filtros.territorio,
      },
      controller.signal,
    )
      .then(setLinhas)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o orçamento. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [
    filtros.meta,
    filtros.rubrica,
    filtros.estado,
    filtros.territorio,
    reloadKey,
  ]);

  // ── Montagem da tela ──────────────────────────────────────────────────────
  // O backend devolve uma lista plana de células; agrupar por Meta é só
  // apresentação — nenhum indicador é recalculado aqui.
  const grupos: MetaComRubricas[] = useMemo(() => {
    if (!linhas) return [];
    const porMeta = new Map<number, MetaComRubricas>();

    for (const linha of linhas) {
      let grupo = porMeta.get(linha.meta.id);
      if (!grupo) {
        grupo = { meta: linha.meta, celulas: [] };
        porMeta.set(linha.meta.id, grupo);
      }
      grupo.celulas.push({
        linha,
        nivelSemaforo: nivelDaLinha(linha),
        percentual: percentualComprometido(linha),
        vazia: linhaVazia(linha),
      });
    }

    // A ordem de `metas × rubricas` do backend já é numero/ordem; o Map
    // preserva a ordem de inserção, então não há o que reordenar.
    return [...porMeta.values()];
  }, [linhas]);

  /**
   * As alocações do banner: `alerta_80` é o campo que o backend dedica a isso,
   * e usá-lo (em vez de comparar o percentual aqui) mantém a tela e o e-mail
   * diário disparando no mesmo critério.
   */
  const criticas = useMemo(
    () =>
      grupos.flatMap((g) => g.celulas.filter((c) => c.linha.alerta_80)),
    [grupos],
  );

  /** O nível veio na resposta; a tela só o nomeia. Ver `EscopoExibido`. */
  const escopo: EscopoExibido = useMemo(() => {
    const nivel: NivelOrcamento = linhas?.[0]?.nivel ?? "nacional";
    if (nivel === "estadual") {
      // `value` é a própria sigla (ver fetchStateSiglaOptions), então a opção
      // casa por igualdade — nada de procurar "(PE)" dentro do rótulo.
      const opcao = estados.find((e) => e.value === filtros.estado);
      return { nivel, nomeLocal: opcao?.label ?? (filtros.estado || null) };
    }
    if (nivel === "territorial") {
      const opcao = territorios.find((t) => t.value === filtros.territorio);
      // O ADT não escolhe o território — o backend resolve pelo perfil dele, e
      // o nome não chega na resposta do painel. Sem opção correspondente, o
      // rótulo cai para "Territorial", que continua verdadeiro.
      return { nivel, nomeLocal: opcao?.label ?? null };
    }
    return { nivel, nomeLocal: null };
  }, [linhas, estados, territorios, filtros.estado, filtros.territorio]);

  // Ordenado aqui porque o backend não entrega ordenado: o `annotate(Sum(...))`
  // de `WorkPlanMetaViewSet.get_queryset` derruba o ORDER BY do model, e o
  // viewset não registra `OrderingFilter` — então o `?ordering=numero` que
  // `listMetas` manda também é ignorado. Sem isto o select lista as Metas
  // embaralhadas (4, 7, 5, 6, 2, 1, 3 no banco de demonstração).
  // Ver frontend/docs/pendencias-backend-sprint-9.md.
  const metaOptions: SelectOption[] = useMemo(
    () =>
      [...metas]
        .sort((a, b) => a.numero - b.numero)
        .map((m) => ({
          value: String(m.id),
          label: `Meta ${m.numero} – ${m.titulo}`,
        })),
    [metas],
  );

  // Catálogo fechado do domínio (§5.3.1) — ver `RUBRICAS` em lib/orcamento.ts.
  const rubricaOptions: SelectOption[] = useMemo(
    () => RUBRICAS.map((r) => ({ value: r.slug, label: r.nome })),
    [],
  );

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  if (authLoading) return <CenteredSpinner />;

  const header = (
    <PageHeader>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="truncate text-base font-semibold text-text">
          Painel de Orçamento
        </h1>
        {/* O painel é a leitura; a distribuição (§5.3.2) é a escrita que o
            alimenta. Só aparece para quem o backend deixaria gravar.

            `as="a"` é obrigatório: `isAnchor` do Button testa `as === "a"`, não
            a presença de `href`. Sem ele sai um <button> com um href
            decorativo, que não navega para lugar nenhum. */}
        {podeDistribuir && (
          <Button
            as="a"
            size="sm"
            variant="secondary"
            href="/sgp/orcamento/distribuicao"
            data-testid="orcamento-ir-distribuicao"
          >
            Distribuir
          </Button>
        )}
      </div>
    </PageHeader>
  );

  if (forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const temFiltro =
    filtros.meta !== "" ||
    filtros.rubrica !== "" ||
    filtros.estado !== "" ||
    filtros.territorio !== "";

  // Só a primeira carga troca a tela pelo skeleton. Depois disso a matriz
  // anterior fica visível e esmaecida: piscar a página inteira a cada mexida
  // num Select custa mais orientação do que entrega.
  const primeiraCarga = loading && linhas === null;

  // `painel_orcamento` emite uma linha por par Meta × rubrica ativa, zeros
  // inclusive — uma Meta sem orçamento volta como 6 linhas zeradas, nunca uma
  // lista vazia. Sem este teste a tela mostraria uma matriz de "R$ 0,00" onde o
  // certo é dizer que não há orçamento lançado.
  const semOrcamento =
    !loading &&
    !error &&
    (grupos.length === 0 || grupos.every((g) => g.celulas.every((c) => c.vazia)));

  return (
    <div data-testid="orcamento-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Orçamento" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Matriz Meta × Rubrica do orçamento do PDHC III. O semáforo compara o
          valor comprometido com o aprovado de cada rubrica; a partir de 80% a
          alocação entra no alerta do topo.
        </p>

        <OrcamentoFilters
          value={filtros}
          onChange={patchFiltros}
          onClear={limparFiltros}
          metaOptions={metaOptions}
          rubricaOptions={rubricaOptions}
          estadoOptions={estados}
          territorioOptions={territorios}
          optionsLoading={metas.length === 0}
          soTerritorio={soTerritorio}
        />

        {/* Só para o ADT/ACR: para os demais perfis a própria matriz já mostra
            estes números no nível que lhes cabe, e o card seria redundante. */}
        {soTerritorio && (
          <BudgetBalance
            metaId={filtros.meta || null}
            titulo="Saldo por rubrica no seu território"
          />
        )}

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button variant="secondary" onClick={reload}>
              Tentar novamente
            </Button>
          </div>
        ) : primeiraCarga ? (
          <MatrizSkeleton />
        ) : semOrcamento ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Wallet className="h-7 w-7" />}
              title={
                temFiltro
                  ? "Nenhum orçamento para este recorte"
                  : "Nenhum orçamento lançado ainda"
              }
              description={
                temFiltro
                  ? "As Metas e rubricas deste recorte não têm valores lançados. Ajuste os filtros para ver outras combinações."
                  : "Assim que a UGP distribuir o orçamento entre as Metas e rubricas, os valores aparecem aqui."
              }
              action={
                temFiltro ? (
                  <Button
                    variant="secondary"
                    onClick={limparFiltros}
                    data-testid="orcamento-vazio-limpar"
                  >
                    Limpar filtros
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <div
            aria-busy={loading}
            className={`flex flex-col gap-4 transition-opacity ${
              loading ? "opacity-60" : ""
            }`}
          >
            <AlertaAlocacoesCriticas
              celulas={criticas}
              onSelect={setSelecionada}
            />

            <MatrizOrcamento
              grupos={grupos}
              escopo={escopo}
              onSelect={setSelecionada}
            />
          </div>
        )}
      </div>

      <CelulaDetalheSlideOver
        celula={selecionada}
        onClose={() => setSelecionada(null)}
        soTerritorio={soTerritorio}
      />
    </div>
  );
}

/**
 * `useSearchParams` exige um limite de Suspense acima dele — mesmo padrão já
 * usado no painel do PT, no detalhe da Meta e nas telas de login.
 */
export default function PainelOrcamentoPage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <PainelOrcamentoConteudo />
    </Suspense>
  );
}
