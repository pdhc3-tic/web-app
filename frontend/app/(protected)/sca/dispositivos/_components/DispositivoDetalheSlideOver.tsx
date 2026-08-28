"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Smartphone } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  getDevice,
  statusConexao,
  type StatusConexao,
  type SyncDeviceDetail,
  type SyncDeviceListItem,
} from "@/app/lib/sca";
import { SemaforoBadge } from "./SemaforoBadge";

type Props = {
  open: boolean;
  onClose: () => void;
  /**
   * Item da tabela — usado para pré-carregar nome/técnico enquanto o detalhe
   * chega, evitando piscar "carregando" no header.
   */
  device: SyncDeviceListItem | null;
  /**
   * Vem do payload da listagem (`limiar_alerta_dias`) para classificar o
   * semáforo do dispositivo aberto — mesma regra usada na tabela.
   */
  limiarAlertaDias: number;
};

/**
 * Detalhe do dispositivo SCA (#156).
 *
 * Consome `GET /api/v1/sca/devices/{id}/` — payload igual ao da listagem, mais
 * `registros_por_entidade` (dict entidade→contagem) e `criado_em`.
 *
 * A "história de sincronizações" propriamente dita mora na FE-12/#157 (log de
 * sincronização com paginação, filtros por tipo/data etc.); daqui o único link
 * é o botão "Ver log completo" no rodapé, apontando para essa tela filtrada
 * pelo id do dispositivo.
 */
export function DispositivoDetalheSlideOver({
  open,
  onClose,
  device,
  limiarAlertaDias,
}: Props) {
  const [detalhe, setDetalhe] = useState<SyncDeviceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !device) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetalhe(null);
    setError(null);
    setLoading(true);

    getDevice(device.id, controller.signal)
      .then((d) => setDetalhe(d))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o dispositivo.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [open, device]);

  const title = device
    ? device.nome || device.device_id || "Dispositivo"
    : "Dispositivo";

  // Semáforo do header: usa o detalhe quando disponível para refletir contagem
  // atualizada; enquanto carrega, usa a linha da tabela para não piscar.
  const fonte = detalhe ?? device;
  const status: StatusConexao | null = fonte
    ? statusConexao(fonte, limiarAlertaDias)
    : null;

  const footer = (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={onClose}>
        Fechar
      </Button>
      <Button
        as="a"
        href={
          device
            ? `/sca/sync-events?device=${device.id}`
            : "/sca/sync-events"
        }
        rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
        data-testid="dispositivo-ver-log"
      >
        Ver log completo
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={title}
      badge={status ? <SemaforoBadge status={status} /> : undefined}
      footer={footer}
      width="wide"
    >
      {loading && !detalhe ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      ) : error ? (
        <div className="px-4 py-6">
          <p className="text-sm text-error-text">{error}</p>
        </div>
      ) : detalhe ? (
        <Corpo detalhe={detalhe} />
      ) : null}
    </SlideOver>
  );
}

function Corpo({ detalhe }: { detalhe: SyncDeviceDetail }) {
  const territoriosBloco =
    detalhe.territorios.length === 0 ? (
      <span className="text-text-muted">—</span>
    ) : (
      <div className="flex flex-wrap gap-1.5">
        {detalhe.territorios.map((t) => (
          <Chip key={t.id}>{t.nome}</Chip>
        ))}
      </div>
    );

  const pendentes = Object.entries(detalhe.registros_por_entidade ?? {}).filter(
    ([, n]) => n > 0,
  );

  return (
    <div className="flex flex-col gap-6 px-4 py-4">
      <section>
        <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
          Dispositivo
        </h3>
        <DefinitionList
          items={[
            {
              label: "Nome",
              value: (
                <span className="inline-flex items-center gap-1.5">
                  <Smartphone className="h-3.5 w-3.5 text-text-muted" />
                  {detalhe.nome || detalhe.device_id}
                </span>
              ),
            },
            { label: "Identificador", value: detalhe.device_id },
            { label: "Modelo", value: detalhe.modelo },
            { label: "Sistema", value: detalhe.sistema_operacional },
            { label: "Versão do app", value: detalhe.app_versao },
            { label: "Ativo", value: detalhe.ativo ? "Sim" : "Não" },
          ]}
        />
      </section>

      <section>
        <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
          Técnico
        </h3>
        <DefinitionList
          items={[
            { label: "Nome", value: detalhe.tecnico.nome },
            { label: "E-mail", value: detalhe.tecnico.email },
            { label: "Território", value: territoriosBloco },
          ]}
        />
      </section>

      <section>
        <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
          Sincronização
        </h3>
        <DefinitionList
          items={[
            {
              label: "Última sincronização",
              value: detalhe.ultimo_sync_servidor ? (
                <span title={absoluteDateTime(detalhe.ultimo_sync_servidor)}>
                  {relativeTime(detalhe.ultimo_sync_servidor)}
                </span>
              ) : (
                <span className="text-text-muted">Nunca sincronizou</span>
              ),
            },
            {
              label: "Registros pendentes",
              value: (
                <span className="font-mono tabular-nums">
                  {detalhe.registros_pendentes}
                </span>
              ),
            },
          ]}
        />
        {pendentes.length > 0 && (
          <div className="mt-3 rounded-md border border-border bg-surface-muted/40 p-3">
            <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-text-muted">
              Pendentes por entidade
            </p>
            <ul className="flex flex-col gap-1 text-sm">
              {pendentes.map(([entidade, n]) => (
                <li
                  key={entidade}
                  className="flex items-center justify-between gap-4"
                >
                  <span className="capitalize text-text">{entidade}</span>
                  <span className="font-mono tabular-nums text-text-muted">
                    {n}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-3 text-xs text-text-muted">
          O histórico completo de sincronizações (push/pull, erros por item)
          fica na tela de Log — use o botão abaixo.
        </p>
      </section>
    </div>
  );
}
