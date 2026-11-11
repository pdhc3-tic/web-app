"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  desativarUsuario,
  fetchImpactoDesativacao,
  type ImpactoDesativacao,
  type UserListItem,
} from "@/app/lib/users";
import { useRotuloChoice } from "@/app/providers/SgpChoicesProvider";

type Props = {
  /** O usuário a desativar; `null` fecha o diálogo. */
  usuario: UserListItem | null;
  onClose: () => void;
  onDesativado: (usuario: UserListItem) => void;
};

/**
 * Desativação de usuário com aviso de impacto (#406, CORE-RF11).
 *
 * Antes de desativar, mostra o que `GET /core/usuarios/{id}/impacto-desativacao/`
 * devolve: as demandas que serão canceladas e o saldo que volta para as
 * rubricas. O botão só libera depois que o impacto carregou e a pessoa marcou
 * a confirmação. Se o impacto não carregar, não dá para desativar às cegas.
 */
export function DesativarUsuarioDialog({ usuario, onClose, onDesativado }: Props) {
  const statusLabel = useRotuloChoice("demanda_status");
  const [impacto, setImpacto] = useState<ImpactoDesativacao | null>(null);
  const [erroImpacto, setErroImpacto] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [ciente, setCiente] = useState(false);
  const [desativando, setDesativando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const userId = usuario?.id ?? null;

  useEffect(() => {
    if (userId === null) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setImpacto(null);
    setErroImpacto(null);
    setCiente(false);
    setErro(null);
    fetchImpactoDesativacao(userId, controller.signal)
      .then(setImpacto)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setErroImpacto(
          e instanceof ApiError ? e.message : "Não foi possível calcular o impacto da desativação.",
        );
      });
    return () => controller.abort();
  }, [userId, tentativa]);

  async function confirmar() {
    if (!usuario || !impacto || !ciente || desativando) return;
    setErro(null);
    setDesativando(true);
    try {
      await desativarUsuario(usuario.id);
      onDesativado(usuario);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível desativar o usuário. Tente novamente.");
    } finally {
      setDesativando(false);
    }
  }

  const semImpacto = impacto !== null && impacto.demandas.length === 0;

  return (
    <SlideOver
      open={usuario !== null}
      onClose={desativando ? () => {} : onClose}
      title="Desativar usuário"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={desativando}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={() => void confirmar()}
            disabled={!impacto || !ciente}
            loading={desativando}
            data-testid="desativar-confirmar"
          >
            Desativar usuário
          </Button>
        </div>
      }
    >
      {usuario && (
        <div className="flex flex-col gap-5 px-4 py-6" data-testid="desativar-usuario-dialog">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-5 w-5" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-text">
                Desativar <span className="font-semibold">{usuario.nome_completo}</span>?
              </p>
              <p className="mt-1 text-sm leading-relaxed text-text-muted">
                A pessoa perde o acesso ao sistema. As demandas dela que ainda não foram autorizadas são
                canceladas, e o saldo que reservavam volta para as rubricas.
              </p>
            </div>
          </div>

          {erroImpacto ? (
            <div
              role="alert"
              className="flex flex-col items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
              data-testid="desativar-impacto-erro"
            >
              {erroImpacto}
              <Button variant="secondary" size="sm" onClick={() => setTentativa((n) => n + 1)}>
                Tentar de novo
              </Button>
            </div>
          ) : !impacto ? (
            <p role="status" className="flex items-center gap-2 text-sm text-text-muted" data-testid="desativar-impacto-carregando">
              <Spinner className="h-4 w-4 animate-spin" /> Calculando o impacto…
            </p>
          ) : semImpacto ? (
            <p
              className="rounded-md border border-border bg-surface-muted/50 px-3 py-2.5 text-sm text-text-muted"
              data-testid="desativar-sem-impacto"
            >
              Nenhuma demanda será cancelada e nenhum saldo será liberado.
            </p>
          ) : (
            <div className="flex flex-col gap-4" data-testid="desativar-impacto">
              <section aria-labelledby="impacto-demandas-titulo" className="flex flex-col gap-2">
                <h3 id="impacto-demandas-titulo" className="text-sm font-semibold text-text">
                  Demandas que serão canceladas ({impacto.demandas.length})
                </h3>
                <ul className="divide-y divide-border rounded-md border border-border">
                  {impacto.demandas.map((d) => (
                    <li
                      key={d.id}
                      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 px-3 py-2"
                      data-testid={`impacto-demanda-${d.id}`}
                    >
                      <span className="min-w-0 flex-1 truncate text-sm text-text">{d.titulo}</span>
                      <span className="text-xs text-text-muted">{statusLabel(d.status)}</span>
                      <span className="text-sm tabular-nums text-text">{formatCurrencyBRL(d.saldo_liberado)}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-labelledby="impacto-saldo-titulo" className="flex flex-col gap-2">
                <h3 id="impacto-saldo-titulo" className="text-sm font-semibold text-text">
                  Saldo que será liberado
                </h3>
                <dl className="rounded-md border border-border">
                  {impacto.saldo_por_rubrica.map((r) => (
                    <div
                      key={r.rubrica_id}
                      className="flex items-center justify-between gap-3 border-b border-border px-3 py-2 text-sm"
                      data-testid={`impacto-rubrica-${r.rubrica_id}`}
                    >
                      <dt className="text-text-muted">{r.rubrica_nome}</dt>
                      <dd className="tabular-nums text-text">{formatCurrencyBRL(r.valor)}</dd>
                    </div>
                  ))}
                  <div className="flex items-center justify-between gap-3 px-3 py-2 text-sm font-semibold">
                    <dt className="text-text">Total</dt>
                    <dd className="tabular-nums text-text" data-testid="impacto-total">
                      {formatCurrencyBRL(impacto.saldo_liberado)}
                    </dd>
                  </div>
                </dl>
              </section>
            </div>
          )}

          {impacto && (
            <label className="flex cursor-pointer items-start gap-2 text-sm text-text">
              <input
                type="checkbox"
                className="mt-0.5 accent-primary"
                checked={ciente}
                disabled={desativando}
                onChange={(e) => setCiente(e.target.checked)}
                data-testid="desativar-ciente"
              />
              {semImpacto
                ? "Confirmo que quero desativar este usuário."
                : "Estou ciente de que as demandas acima serão canceladas e confirmo a desativação."}
            </label>
          )}

          {erro && (
            <p
              role="alert"
              className="rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
              data-testid="desativar-erro"
            >
              {erro}
            </p>
          )}
        </div>
      )}
    </SlideOver>
  );
}
