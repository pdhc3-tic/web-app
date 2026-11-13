"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import { absoluteDateTime } from "@/app/lib/datetime";
import {
  PARAMETROS,
  fetchConfigs,
  salvarConfig,
  validarParametro,
  valorDeTela,
  type ConfigDoSistema,
  type DefinicaoParametro,
} from "@/app/lib/parametrosOrcamento";
import { qk } from "@/app/lib/queryKeys";

const CONTROLE =
  "h-9 rounded-md border border-border bg-surface px-3 text-sm text-text outline-none transition-colors hover:border-text-muted focus:border-primary disabled:cursor-not-allowed disabled:opacity-70";

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Configurações</h1>
    </PageHeader>
  );
}

/**
 * Uma linha do painel: o controle certo para o tipo do parâmetro, a validação
 * de tipo e de faixa antes do envio e o Salvar só quando o valor mudou.
 */
function LinhaParametro({ def, config }: { def: DefinicaoParametro; config: ConfigDoSistema | undefined }) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const salvo = valorDeTela(def, config?.valor);
  const [valor, setValor] = useState(salvo);
  const [erroDoServidor, setErroDoServidor] = useState<string | null>(null);

  const erro = validarParametro(def, valor);
  const mudou = valor.trim() !== salvo;

  const salvar = useMutation({
    mutationFn: () => salvarConfig(def.chave, valor.trim()),
    onSuccess: async () => {
      setErroDoServidor(null);
      await queryClient.invalidateQueries({ queryKey: qk.systemConfig });
      showToast(`"${def.rotulo}" atualizado.`, "success");
    },
    onError: (e) => {
      setErroDoServidor(
        e instanceof ApiError
          ? (e.fieldErrors?.find((f) => f.field === "valor")?.message ?? e.message)
          : "Não foi possível salvar o parâmetro.",
      );
    },
  });

  function mudar(novo: string) {
    setValor(novo);
    setErroDoServidor(null);
  }

  const idControle = `parametro-${def.chave}`;
  const mensagem = (mudou ? erro : null) ?? erroDoServidor;

  return (
    <li className="flex flex-col gap-3 px-5 py-4" data-testid={`parametro-${def.chave}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 flex-1 basis-64">
          <label htmlFor={idControle} className="text-sm font-medium text-text">
            {def.rotulo}
          </label>
          <p className="mt-0.5 text-sm text-text-muted">{def.ajuda}</p>
          <p className="mt-1 font-mono text-xs text-text-muted">{def.chave}</p>
        </div>

        <div className="flex items-center gap-2">
          {def.controle === "opcoes" ? (
            <select
              id={idControle}
              className={CONTROLE}
              value={valor}
              disabled={!config || salvar.isPending}
              onChange={(e) => mudar(e.target.value)}
            >
              {/* Valor fora da lista (legado): aparece, mas não pode ser salvo. */}
              {!def.opcoes.some((o) => o.value === valor) && <option value={valor}>{valor || "Não definido"}</option>}
              {def.opcoes.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : def.controle === "booleano" ? (
            <select
              id={idControle}
              className={CONTROLE}
              value={valor}
              disabled={!config || salvar.isPending}
              onChange={(e) => mudar(e.target.value)}
            >
              <option value="true">Ligado</option>
              <option value="false">Desligado</option>
            </select>
          ) : (
            <span className="flex items-center gap-1.5">
              <input
                id={idControle}
                type="text"
                inputMode="numeric"
                className={`${CONTROLE} w-24 text-right tabular-nums ${mensagem ? "border-error-text" : ""}`}
                value={valor}
                disabled={!config || salvar.isPending}
                aria-invalid={mensagem ? true : undefined}
                aria-describedby={mensagem ? `${idControle}-erro` : undefined}
                onChange={(e) => mudar(e.target.value)}
              />
              <span className="text-sm text-text-muted">{def.unidade}</span>
            </span>
          )}
          <Button
            size="sm"
            disabled={!config || !mudou || erro !== null}
            loading={salvar.isPending}
            onClick={() => salvar.mutate()}
            data-testid={`parametro-salvar-${def.chave}`}
          >
            Salvar
          </Button>
        </div>
      </div>

      {mensagem && (
        <p id={`${idControle}-erro`} role="alert" className="text-sm text-error-text" data-testid={`parametro-erro-${def.chave}`}>
          {mensagem}
        </p>
      )}
      {!config ? (
        <p className="text-xs text-warning-text">Parâmetro ainda não cadastrado no backend.</p>
      ) : (
        config.atualizado_em && (
          <p className="text-xs text-text-muted">
            Última alteração em {absoluteDateTime(config.atualizado_em)}
            {config.atualizado_por ? ` por ${config.atualizado_por}` : ""}.
          </p>
        )
      )}
    </li>
  );
}

/**
 * Parâmetros globais do orçamento (#403, CORE-RF16/RF17): periodicidade e
 * acúmulo dos limites, sobrealocação e os limiares dos alertas de subexecução
 * e de remanejamento. Só Super Admin, como as demais telas de Configurações.
 */
export default function ParametrosOrcamentoPage() {
  const { loading, isSuperAdmin } = useIsSuperAdmin();

  const configs = useQuery({
    queryKey: qk.systemConfig,
    queryFn: ({ signal }) => fetchConfigs(signal),
    enabled: !loading && isSuperAdmin,
  });

  if (loading) {
    return (
      <>
        <HeaderSlot />
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      </>
    );
  }

  if (!isSuperAdmin) {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  const porChave = new Map((configs.data ?? []).map((c) => [c.chave, c]));

  return (
    <>
      <HeaderSlot />
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Configurações", href: "/admin/configuracoes" },
            { label: "Parâmetros do orçamento" },
          ]}
        />
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Parâmetros do orçamento</h2>
          <p className="mt-1 text-sm text-text-muted">
            Valem para todo o projeto. Cada parâmetro é salvo separadamente e fica registrado quem o alterou.
          </p>
        </div>

        {configs.isPending ? (
          <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
            <Spinner className="h-4 w-4 animate-spin" /> Carregando parâmetros…
          </p>
        ) : configs.error ? (
          <TabErroSection
            message={
              configs.error instanceof ApiError ? configs.error.message : "Não foi possível carregar os parâmetros."
            }
            onRetry={() => void configs.refetch()}
          />
        ) : (
          <ul
            className="divide-y divide-border rounded-lg border border-border bg-surface"
            data-testid="parametros-orcamento"
          >
            {PARAMETROS.map((def) => {
              const config = porChave.get(def.chave);
              // A `key` com o valor salvo remonta a linha depois de salvar.
              return <LinhaParametro key={`${def.chave}:${config?.valor ?? ""}`} def={def} config={config} />;
            })}
          </ul>
        )}
      </div>
    </>
  );
}
