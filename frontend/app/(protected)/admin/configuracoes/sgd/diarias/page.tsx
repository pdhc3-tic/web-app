"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { ConfirmDeleteDialog } from "@/app/components/ui/ConfirmDeleteDialog/ConfirmDeleteDialog";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { ApiError } from "@/app/lib/api";
import { canConfigurarDiarias, isSuperAdmin } from "@/app/lib/auth/roles";
import { formatDate } from "@/app/lib/datetime";
import {
  excluirValor,
  lerParametros,
  listarFaixas,
  listarValores,
  type ValorDiaria,
} from "@/app/lib/diarias";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { GradeValores } from "./_components/GradeValores";
import { MunicipiosDaFaixa } from "./_components/MunicipiosDaFaixa";
import { ParametrosContagem } from "./_components/ParametrosContagem";
import { ValorDialog, type AlvoDoValor } from "./_components/ValorDialog";

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Tabela de diárias</h1>
    </PageHeader>
  );
}

const mensagemDe = (erro: unknown, padrao: string) => (erro instanceof ApiError ? erro.message : padrao);

/**
 * Configuração da tabela de diárias (#366, SGD §3.1): valores por faixa de
 * destino e vigência, municípios de cada faixa e parâmetros de contagem.
 * Super Admin e FGD, como as escritas de `/sgd/config/diarias/`.
 */
export default function TabelaDiariasPage() {
  const { data: session, status } = useSession();
  const queryClient = useQueryClient();
  const carregandoSessao = status === "loading";
  const podeConfigurar = canConfigurarDiarias(session?.user);
  const habilitado = !carregandoSessao && podeConfigurar;

  const faixas = useQuery({
    queryKey: qk.diarias.faixas,
    queryFn: ({ signal }) => listarFaixas(signal),
    enabled: habilitado,
  });
  const valores = useQuery({
    queryKey: qk.diarias.valores,
    queryFn: ({ signal }) => listarValores(signal),
    enabled: habilitado,
  });
  const parametros = useQuery({
    queryKey: qk.diarias.parametros,
    queryFn: ({ signal }) => lerParametros(signal),
    enabled: habilitado,
  });

  const [alvo, setAlvo] = useState<AlvoDoValor | null>(null);
  const [aExcluir, setAExcluir] = useState<ValorDiaria | null>(null);

  if (carregandoSessao) {
    return (
      <>
        <HeaderSlot />
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      </>
    );
  }

  if (!podeConfigurar) {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  // O hub de Configurações é só do Super Admin; a FGD chega aqui pelo SGD.
  const trilha = isSuperAdmin(session?.user)
    ? [
        { label: "Início", href: "/dashboard" },
        { label: "Configurações", href: "/admin/configuracoes" },
        { label: "Tabela de diárias" },
      ]
    : [{ label: "Início", href: "/dashboard" }, { label: "SGD", href: "/sgd" }, { label: "Tabela de diárias" }];

  const listaDeFaixas = faixas.data;
  const listaDeValores = valores.data;
  const erroDaTabela = faixas.error ?? valores.error;
  const p = parametros.data;

  return (
    <>
      <HeaderSlot />
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <Breadcrumb items={trilha} />
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Tabela de diárias</h2>
          <p className="mt-1 text-sm text-text-muted">
            O valor de cada solicitação de diária sai daqui: a faixa do município de destino, o valor vigente na data
            da viagem e as regras de contagem.
          </p>
        </div>

        {erroDaTabela ? (
          <TabErroSection
            message={mensagemDe(erroDaTabela, "Não foi possível carregar a tabela de diárias.")}
            onRetry={() => {
              void faixas.refetch();
              void valores.refetch();
            }}
          />
        ) : !listaDeFaixas || !listaDeValores ? (
          <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
            <Spinner className="h-4 w-4 animate-spin" /> Carregando a tabela de diárias…
          </p>
        ) : (
          <>
            <section className="flex flex-col gap-3" aria-labelledby="diarias-valores-titulo">
              <div>
                <h3 id="diarias-valores-titulo" className="text-base font-semibold text-text">
                  Valores por faixa de destino e vigência
                </h3>
                <p className="mt-0.5 text-sm text-text-muted">
                  Editar um valor não apaga o anterior: ele é encerrado na véspera da nova vigência e fica no
                  histórico.
                </p>
              </div>
              {listaDeFaixas.length === 0 ? (
                <p className="rounded-lg border border-border bg-surface px-5 py-6 text-sm text-text-muted">
                  Nenhuma faixa de destino cadastrada.
                </p>
              ) : (
                <GradeValores
                  faixas={listaDeFaixas}
                  valores={listaDeValores}
                  onEditar={(faixa, atual) => setAlvo({ faixa, atual })}
                  onExcluir={setAExcluir}
                />
              )}
            </section>

            <section className="flex flex-col gap-3" aria-labelledby="diarias-municipios-titulo">
              <div>
                <h3 id="diarias-municipios-titulo" className="text-base font-semibold text-text">
                  Municípios de cada faixa
                </h3>
                <p className="mt-0.5 text-sm text-text-muted">
                  O município sem enquadramento cai na faixa das capitais, se for capital, ou na das demais
                  localidades.
                </p>
              </div>
              <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
                {listaDeFaixas.map((faixa) => (
                  // A `key` com os códigos salvos remonta o bloco depois de salvar.
                  <MunicipiosDaFaixa
                    key={`${faixa.id}:${faixa.enquadramentos.map((m) => m.codigo_ibge).join(",")}`}
                    faixa={faixa}
                  />
                ))}
              </ul>
            </section>
          </>
        )}

        <section className="flex flex-col gap-3" aria-labelledby="diarias-parametros-titulo">
          <div>
            <h3 id="diarias-parametros-titulo" className="text-base font-semibold text-text">
              Parâmetros de contagem
            </h3>
            <p className="mt-0.5 text-sm text-text-muted">
              Valem para as solicitações calculadas daqui em diante. As já gravadas não mudam.
            </p>
          </div>
          {parametros.isPending ? (
            <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
              <Spinner className="h-4 w-4 animate-spin" /> Carregando os parâmetros…
            </p>
          ) : parametros.error || !p ? (
            <TabErroSection
              message={mensagemDe(parametros.error, "Não foi possível carregar os parâmetros de contagem.")}
              onRetry={() => void parametros.refetch()}
            />
          ) : (
            <ParametrosContagem key={JSON.stringify(p)} parametros={p} />
          )}
        </section>
      </div>

      <ValorDialog alvo={alvo} onClose={() => setAlvo(null)} />

      <ConfirmDeleteDialog
        open={aExcluir !== null}
        onClose={() => setAExcluir(null)}
        title="Excluir valor da diária"
        itemName={
          aExcluir
            ? `${formatCurrencyBRL(aExcluir.valor)} de ${aExcluir.faixa_destino_nome}, a partir de ${formatDate(aExcluir.vigencia_inicio)}`
            : ""
        }
        description="Só sai da tabela o valor que ainda não vigorou e que nenhuma solicitação usou. A vigência anterior volta a cobrir o período."
        onConfirm={async () => {
          if (!aExcluir) return;
          await excluirValor(aExcluir.id);
          await queryClient.invalidateQueries({ queryKey: qk.diarias.valores });
        }}
      />
    </>
  );
}
