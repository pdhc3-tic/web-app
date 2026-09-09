"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  AlertTriangle,
  CalendarX,
  Check,
  Compass,
  Handshake,
  History,
  ImagePlus,
  MapPin,
  RefreshCw,
  Pencil,
  User,
  Users,
} from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { OrigemScaBadge } from "@/app/components/sgp/OrigemScaBadge";
import { EvidenceGallery } from "@/app/components/sgp/EvidenceGallery/EvidenceGallery";
import { TransicaoStatusDialog } from "./_components/TransicaoStatusDialog";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { isStatusTerminal } from "@/app/lib/atividades";
import { ApiError } from "@/app/lib/api";
import {
  badgeStatusFor,
  getAtividade,
  statusLabel,
  type AtividadeDetail,
} from "@/app/lib/atividades";
import { listMembros } from "@/app/lib/membros";
import {
  absoluteDateTime,
  formatDate,
  formatTimeRange,
  relativeTime,
} from "@/app/lib/datetime";

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function HeaderSlot() {
  return (
    <PageHeader>
      <span className="truncate text-base font-semibold text-text">
        Atividades
      </span>
    </PageHeader>
  );
}

/**
 * Ficha da Atividade — leitura.
 *
 * Até aqui a lista levava direto ao formulário de edição, e o painel do
 * calendário oferecia "abrir ficha completa" apontando para o mesmo formulário.
 * Ver uma atividade exigia entrar no modo de edição dela, o que é desconfortável
 * para quem só quer consultar — e impossível para quem não tem permissão de
 * escrita.
 */
export default function AtividadeFichaPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [atividade, setAtividade] = useState<AtividadeDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [transicaoAberta, setTransicaoAberta] = useState(false);
  /**
   * Modo "anexar evidência", ligado pelo atalho do modal de transição.
   *
   * A ficha é de leitura e a galeria nasce `readOnly` — o upload mora no
   * formulário de edição. Só que o atalho do aviso "falta evidência para
   * concluir" rolava até essa mesma galeria travada: o botão prometia anexar e
   * levava a um bloco sem nenhum controle de upload. Em vez de mandar o técnico
   * ao formulário inteiro (com todo o risco de alteração acidental que motivou
   * esta ficha), a galeria destrava aqui, por um pedido explícito e reversível.
   */
  const [anexando, setAnexando] = useState(false);
  /**
   * Recarga que NÃO troca a tela pelo spinner. Serve ao retorno do modo de
   * anexo: `fotos`/`documentos` do detalhe é o que decide se "Concluído" pode
   * ser oferecido, e ele fica velho assim que a galeria grava um arquivo.
   */
  const silenciosaRef = useRef(false);
  const { showToast } = useToast();

  useEffect(() => {
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }
    const controller = new AbortController();
    if (!silenciosaRef.current) setStatus("loading");
    // Consome a marca: uma troca de `id` depois disto merece o spinner.
    silenciosaRef.current = false;

    getAtividade(id, controller.signal)
      .then((data) => {
        setAtividade(data);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) setStatus("notfound");
        else if (e instanceof ApiError && e.status === 403)
          setStatus("forbidden");
        else setStatus("error");
      });

    return () => controller.abort();
  }, [id, reloadKey]);

  const terminal = atividade ? isStatusTerminal(atividade.status) : false;

  if (status === "notfound") {
    notFound();
  }

  if (status === "forbidden") {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  if (status === "loading" || !atividade) {
    if (status === "error") {
      return (
        <>
          <HeaderSlot />
          <div className="mx-auto flex min-h-[40vh] max-w-4xl flex-col items-center justify-center gap-4 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              Não foi possível carregar a atividade. Tente novamente.
            </p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        </>
      );
    }
    return (
      <>
        <HeaderSlot />
        <div
          role="status"
          className="mx-auto flex min-h-[40vh] max-w-4xl items-center justify-center gap-2 text-sm text-text-muted"
        >
          <Spinner className="h-5 w-5 animate-spin" />
          Carregando atividade…
        </div>
      </>
    );
  }

  function sairDoModoAnexo() {
    setAnexando(false);
    // Recarrega em silêncio: é o detalhe que carrega `fotos`/`documentos`, e é
    // deles que o modal tira o "falta evidência para concluir".
    silenciosaRef.current = true;
    setReloadKey((k) => k + 1);
  }

  const periodo =
    atividade.data_inicio === atividade.data_fim
      ? formatDate(atividade.data_inicio)
      : `${formatDate(atividade.data_inicio)} — ${formatDate(atividade.data_fim)}`;

  return (
    <>
      <HeaderSlot />

      <div
        data-testid="atividade-ficha-page"
        className="mx-auto flex max-w-4xl flex-col gap-6"
      >
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Atividades", href: "/sgp/atividades" },
            { label: atividade.titulo },
          ]}
        />

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold tracking-tight text-text">
              {atividade.titulo}
            </h1>
            <p className="mt-1 text-sm text-text-muted">
              {atividade.tipo_atividade_display} · {periodo}
              {formatTimeRange(atividade.data_inicio, atividade.data_fim)
                ? ` · ${formatTimeRange(atividade.data_inicio, atividade.data_fim)}`
                : ""}
            </p>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge
                status={badgeStatusFor(atividade.status)}
                label={atividade.status_display || statusLabel(atividade.status)}
              />
              {atividade.atrasada && (
                <Badge status="atrasada" label="Atrasada" />
              )}
              {atividade.google_calendar_sync_status === "erro" && (
                /* RF24: avisa, mas não bloqueia a página — a falha é da
                   integração com a agenda, não do registro da atividade. */
                <span
                  data-testid="badge-calendar-erro"
                  title="A sincronização com o Google Calendar falhou. A atividade está salva; apenas o evento na agenda não foi criado."
                  className="inline-flex items-center gap-1 rounded-full border border-warning-text bg-warning-bg px-2 py-0.5 text-2xs font-semibold text-warning-text"
                >
                  <CalendarX className="h-3 w-3" aria-hidden="true" />
                  Agenda não sincronizada
                </span>
              )}
              <OrigemScaBadge registro={atividade} />
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {/* Estado terminal não admite saída: o controle aparece, mas
                desabilitado e explicando o porquê — some seria pior, deixaria
                o usuário procurando por ele. */}
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={() => setTransicaoAberta(true)}
              disabled={terminal}
              title={
                terminal
                  ? `"${statusLabel(atividade.status)}" é um estado final: não há transição possível a partir dele.`
                  : "Alterar o status desta atividade"
              }
              data-testid="atividade-status-btn"
            >
              Alterar status
            </Button>
            <Button
              as="a"
              href={`/sgp/atividades/${atividade.id}/editar/`}
              variant="secondary"
              size="sm"
              leftIcon={<Pencil className="h-4 w-4" />}
              data-testid="atividade-editar-btn"
            >
              Editar
            </Button>
          </div>
        </div>

        <section className="rounded-lg border border-border bg-surface p-6">
          <h2 className="mb-4 text-sm font-medium text-text">
            Vínculo com o Plano de Trabalho
          </h2>
          <DefinitionList
            items={[
              {
                label: "Ação",
                value: `${atividade.acao.numero} — ${atividade.acao.descricao}`,
              },
              { label: "Âmbito", value: atividade.ambito_display },
              {
                label: "Forma de atuação",
                value: atividade.forma_atuacao_display,
              },
            ]}
          />
        </section>

        <section
          className="rounded-lg border border-border bg-surface p-6"
          data-testid="atividade-equipe-local"
        >
          <h2 className="mb-4 text-sm font-medium text-text">
            Equipe e local
          </h2>
          <DefinitionList
            items={[
              {
                label: "Técnico responsável",
                value: (
                  <span className="inline-flex items-center gap-1.5">
                    <User className="h-3.5 w-3.5 text-text-muted" aria-hidden />
                    {atividade.tecnico_responsavel.nome}
                  </span>
                ),
              },
              {
                label: "Equipe adicional",
                value:
                  atividade.equipe_adicional.length > 0 ? (
                    <ul
                      className="flex list-none flex-wrap gap-1.5"
                      data-testid="atividade-equipe-adicional"
                    >
                      {atividade.equipe_adicional.map((membro) => (
                        <li key={membro.id}>
                          <Chip>{membro.nome}</Chip>
                        </li>
                      ))}
                    </ul>
                  ) : null,
              },
              {
                label: "Local",
                value: (
                  <span className="inline-flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-text-muted" aria-hidden />
                    {atividade.comunidade
                      ? `${atividade.municipio.nome} · ${atividade.comunidade.nome}`
                      : atividade.municipio.nome}
                  </span>
                ),
              },
              {
                label: "Coordenadas",
                value: <Coordenadas atividade={atividade} />,
              },
              {
                label: "Parceiros",
                value: <Parceiros atividade={atividade} />,
              },
            ]}
          />
        </section>

        <Participantes atividade={atividade} />

        <section
          className="rounded-lg border border-border bg-surface p-6"
          data-testid="atividade-evidencias"
          data-anexando={anexando ? "sim" : "nao"}
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-text">Evidências</h2>
            {anexando && (
              <Button
                size="sm"
                variant="secondary"
                leftIcon={<Check className="h-3.5 w-3.5" />}
                onClick={sairDoModoAnexo}
                data-testid="atividade-anexo-concluir"
              >
                Concluir anexos
              </Button>
            )}
          </div>

          {anexando && (
            <p
              className="mb-4 flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-xs leading-relaxed text-info-text"
              role="status"
              data-testid="atividade-anexo-aviso"
            >
              <ImagePlus className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                Anexe a foto ou o documento abaixo e depois use{" "}
                <strong>Concluir anexos</strong>: a ficha recarrega as
                evidências e o botão de alterar status volta a oferecer
                &quot;Concluído&quot;.
              </span>
            </p>
          )}

          {/* Fora do modo de anexo a galeria é só leitura: o upload e a remoção
              vivem no formulário de edição. */}
          <EvidenceGallery
            atividadeId={String(atividade.id)}
            readOnly={!anexando}
          />
        </section>

        {(atividade.descricao_narrativa ||
          atividade.resultados_alcancados ||
          atividade.justificativa) && (
          <section className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6">
            <h2 className="text-sm font-medium text-text">Registro</h2>

            <Texto titulo="Descrição" conteudo={atividade.descricao_narrativa} />
            <Texto
              titulo="Resultados alcançados"
              conteudo={atividade.resultados_alcancados}
            />
            <Texto titulo="Justificativa" conteudo={atividade.justificativa} />
          </section>
        )}

        <TransicaoStatusDialog
          open={transicaoAberta}
          onClose={() => setTransicaoAberta(false)}
          atividade={atividade}
          onTransicionado={(atualizada) => {
            // Troca o badge na hora, sem recarregar a ficha.
            setAtividade(atualizada);
            showToast(
              `Status alterado para "${statusLabel(atualizada.status)}".`,
              "success",
            );
          }}
          onIrParaEvidencias={() => {
            // Destravar ANTES de rolar: chegar numa galeria ainda somente de
            // leitura era exatamente o que fazia o atalho não cumprir o que
            // prometia.
            setAnexando(true);
            // O scroll espera o próximo quadro para a galeria já estar no modo
            // de edição — ela cresce ao mostrar os controles de upload, e sem
            // isso a rolagem para no lugar errado.
            requestAnimationFrame(() => {
              document
                .querySelector('[data-testid="atividade-evidencias"]')
                ?.scrollIntoView({ behavior: "smooth", block: "start" });
            });
          }}
        />

        <Auditoria atividade={atividade} />

        {!atividade.ativo && (
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <Chip>Excluída</Chip>
            Esta atividade foi removida e está visível apenas para consulta.
          </p>
        )}
      </div>
    </>
  );
}

/**
 * Coordenadas do registro.
 *
 * Aparecem como texto selecionável, e não num mapa: a ficha já é longa e o
 * ponto isolado de uma atividade não pede uma tela de mapa — o que o técnico
 * faz com ele é copiar para o GPS. `latitude`/`longitude` são opcionais no
 * modelo, então o par incompleto vale como ausente.
 */
function Coordenadas({ atividade }: { atividade: AtividadeDetail }) {
  const { latitude, longitude } = atividade;
  if (!latitude || !longitude) return null;

  return (
    <span
      className="inline-flex items-center gap-1.5 font-mono text-xs tabular-nums"
      data-testid="atividade-coordenadas"
    >
      <Compass className="h-3.5 w-3.5 text-text-muted" aria-hidden />
      {latitude}, {longitude}
    </span>
  );
}

/**
 * Parceiros — os DOIS campos do modelo.
 *
 * `parceiros_livres` é o texto que o formulário grava. `parceiros_organizacoes`
 * é um M2M com `core.Organization` que o detalhe devolve como ids crus, sem
 * nome, e `OrganizationViewSet` só deixa super-admin/UGP/Articulador listar —
 * ou seja, o ADT, que é quem mais abre esta ficha, não teria como resolvê-los.
 * Enquanto o backend não aninhar o nome (pedido aberto em
 * docs/pendencias-backend-sprint-9.md), a ficha declara quantos são em vez de
 * imprimir números de banco ou de fingir que não existem.
 */
function Parceiros({ atividade }: { atividade: AtividadeDetail }) {
  const livres = atividade.parceiros_livres?.trim() ?? "";
  const organizacoes = atividade.parceiros_organizacoes?.length ?? 0;

  if (!livres && organizacoes === 0) return null;

  return (
    <span
      className="inline-flex flex-wrap items-baseline gap-x-2 gap-y-1"
      data-testid="atividade-parceiros"
    >
      <Handshake
        className="h-3.5 w-3.5 shrink-0 self-center text-text-muted"
        aria-hidden
      />
      {livres && <span className="whitespace-pre-wrap">{livres}</span>}
      {organizacoes > 0 && (
        <span className="text-xs text-text-muted">
          {livres && "· "}
          {organizacoes === 1
            ? "1 organização parceira cadastrada"
            : `${organizacoes} organizações parceiras cadastradas`}
        </span>
      )}
    </span>
  );
}

/**
 * Procedência do registro: quem criou, quando, e quando mudou pela última vez.
 *
 * `criado_por` vem como id puro — o detalhe não aninha o usuário, e
 * `/api/v1/users/` é `IsSuperAdmin`, então nem dá para resolver por fora. O que
 * a ficha faz é procurar o id entre as pessoas que ELA já tem com nome (o
 * técnico responsável, a equipe adicional, o próprio usuário logado), que
 * cobre a grande maioria das atividades. Sem correspondência, fica o id —
 * dizer "Usuário #12" é honesto; inventar um nome, não.
 */
function Auditoria({ atividade }: { atividade: AtividadeDetail }) {
  const { data: session } = useSession();

  const autor = useMemo(() => {
    const id = atividade.criado_por;
    if (id === null) return null;

    if (String(id) === String(session?.user?.id)) {
      return `${session?.user?.nome_completo ?? "Você"} (você)`;
    }
    if (id === atividade.tecnico_responsavel.id) {
      return atividade.tecnico_responsavel.nome;
    }
    const naEquipe = atividade.equipe_adicional.find((u) => u.id === id);
    if (naEquipe) return naEquipe.nome;

    return `Usuário #${id}`;
  }, [atividade, session]);

  return (
    <section
      className="rounded-lg border border-border bg-surface p-6"
      data-testid="atividade-auditoria"
    >
      <h2 className="mb-4 flex items-center gap-2 text-sm font-medium text-text">
        <History className="h-4 w-4 text-text-muted" aria-hidden="true" />
        Registro e auditoria
      </h2>
      <DefinitionList
        items={[
          { label: "Criado por", value: autor },
          { label: "Criado em", value: absoluteDateTime(atividade.criado_em) },
          {
            label: "Última atualização",
            value: (
              <span title={absoluteDateTime(atividade.atualizado_em)}>
                {absoluteDateTime(atividade.atualizado_em)} (
                {relativeTime(atividade.atualizado_em)})
              </span>
            ),
          },
        ]}
      />
    </section>
  );
}

/**
 * Descobre a UPF de cada membro participante.
 *
 * O membro não tem rota própria: a dele é a aba de membros da UPF
 * (`/sgp/upfs/{id}/#membros`). Só que `MembroListSerializer` não devolve a UPF
 * de origem, então o payload da atividade não diz para qual ficha ir — e foi
 * por isso que os membros ficaram sem navegação enquanto as UPFs tinham link.
 *
 * Com UMA UPF participante a resposta sai de graça: `ActivityDetailSerializer.
 * validate` recusa membro que não pertença às UPFs selecionadas, então o
 * vínculo é garantido pelo próprio contrato. Com mais de uma, `listMembros`
 * resolve o cruzamento; se falhar, o membro volta a ser texto simples — melhor
 * sem link do que apontando para a ficha errada.
 */
function useUpfDoMembro(atividade: AtividadeDetail): Map<number, number> {
  const { upfs_participantes: upfs, membros_participantes: membros } = atividade;
  const [mapa, setMapa] = useState<Map<number, number>>(new Map());

  const upfUnica = upfs.length === 1 ? upfs[0].id : null;
  const chave = `${upfs.map((u) => u.id).join(",")}|${membros.length}`;

  useEffect(() => {
    if (upfUnica !== null || upfs.length === 0 || membros.length === 0) {
      return;
    }
    const controller = new AbortController();

    Promise.all(
      upfs.map((upf) =>
        listMembros(upf.id, controller.signal)
          .then((lista) => lista.map((m) => [m.id, upf.id] as const))
          .catch(() => [] as (readonly [number, number])[]),
      ),
    ).then((pares) => {
      if (controller.signal.aborted) return;
      setMapa(new Map(pares.flat()));
    });

    return () => controller.abort();
    // `chave` resume as UPFs e a contagem de membros; as instâncias mudam a
    // cada render da ficha e reexecutariam o efeito à toa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, upfUnica]);

  if (upfUnica !== null) {
    return new Map(membros.map((m) => [m.id, upfUnica]));
  }
  return mapa;
}

/**
 * UPFs e membros que participaram, cada um com link para a própria ficha.
 *
 * Os dois vêm completos no detalhe desde a Issue #227 — nome, CPF mascarado e
 * parentesco já estão no payload, sem requisição adicional por participante.
 */
function Participantes({ atividade }: { atividade: AtividadeDetail }) {
  const { upfs_participantes: upfs, membros_participantes: membros } = atividade;
  const upfDoMembro = useUpfDoMembro(atividade);

  if (upfs.length === 0 && membros.length === 0) {
    return null;
  }

  const linhaClasse =
    "flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm text-text";
  const linhaNavegavel = `${linhaClasse} transition hover:border-primary/60 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary`;

  return (
    <section
      className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6"
      data-testid="atividade-participantes"
    >
      <h2 className="flex items-center gap-2 text-sm font-medium text-text">
        <Users className="h-4 w-4 text-text-muted" aria-hidden="true" />
        Participantes
        <span className="text-text-muted">({atividade.total_participantes})</span>
      </h2>

      {upfs.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-2xs uppercase tracking-[0.08em] text-text-muted">
            UPFs
          </h3>
          <ul className="grid list-none gap-1.5 sm:grid-cols-2">
            {upfs.map((upf) => (
              <li key={upf.id}>
                <Link
                  href={`/sgp/upfs/${upf.id}/`}
                  className={linhaNavegavel}
                  data-testid={`participante-upf-${upf.id}`}
                >
                  <span className="truncate">{upf.nome_titular}</span>
                  <span className="shrink-0 text-2xs text-text-muted">
                    {upf.municipio.nome}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {membros.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-2xs uppercase tracking-[0.08em] text-text-muted">
            Membros
          </h3>
          <ul className="grid list-none gap-1.5 sm:grid-cols-2">
            {membros.map((membro) => {
              const upfId = upfDoMembro.get(membro.id);
              const conteudo = (
                <>
                  <span className="truncate">{membro.nome_completo}</span>
                  <span className="shrink-0 text-2xs text-text-muted">
                    {membro.grau_parentesco_display}
                  </span>
                </>
              );

              return (
                <li key={membro.id}>
                  {upfId === undefined ? (
                    <span
                      className={linhaClasse}
                      data-testid={`participante-membro-${membro.id}`}
                    >
                      {conteudo}
                    </span>
                  ) : (
                    <Link
                      href={`/sgp/upfs/${upfId}/#membros`}
                      className={linhaNavegavel}
                      data-testid={`participante-membro-${membro.id}`}
                    >
                      {conteudo}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

function Texto({ titulo, conteudo }: { titulo: string; conteudo: string }) {
  if (!conteudo?.trim()) return null;
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-2xs uppercase tracking-[0.08em] text-text-muted">
        {titulo}
      </h3>
      <p className="whitespace-pre-wrap text-sm text-text">{conteudo}</p>
    </div>
  );
}
