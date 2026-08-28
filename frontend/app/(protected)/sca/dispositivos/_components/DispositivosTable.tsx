"use client";

import { Smartphone } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import { statusConexao, type SyncDeviceListItem } from "@/app/lib/sca";
import { SemaforoBadge } from "./SemaforoBadge";

type Props = {
  devices: SyncDeviceListItem[];
  limiarAlertaDias: number;
  loading: boolean;
  /**
   * Clique numa linha — a página pai abre o SlideOver de detalhe (#156). O
   * botão "Ver log completo" do SlideOver leva ao FE-12/#157.
   */
  onRowClick: (device: SyncDeviceListItem) => void;
};

/** Tabela de dispositivos SCA. */
export function DispositivosTable({
  devices,
  limiarAlertaDias,
  loading,
  onRowClick,
}: Props) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-surface">
      {loading && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-surface/60">
          <Spinner className="h-5 w-5 animate-spin text-text-muted" />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-220 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Dispositivo</th>
              <th className="px-4 py-2.5">Técnico</th>
              <th className="px-4 py-2.5">Território</th>
              <th className="px-4 py-2.5">Última sincronização</th>
              <th className="px-4 py-2.5 text-right">Pendentes</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <LinhaDispositivo
                key={d.id}
                device={d}
                limiarAlertaDias={limiarAlertaDias}
                onClick={onRowClick}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LinhaDispositivo({
  device,
  limiarAlertaDias,
  onClick,
}: {
  device: SyncDeviceListItem;
  limiarAlertaDias: number;
  onClick: (device: SyncDeviceListItem) => void;
}) {
  const status = statusConexao(device, limiarAlertaDias);
  const ultimo = device.ultimo_sync_servidor;

  return (
    <tr
      onClick={() => onClick(device)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick(device);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`Abrir detalhes do dispositivo ${device.nome || device.device_id}`}
      className="cursor-pointer border-t border-border align-middle outline-none transition hover:bg-surface-muted/40 focus-visible:bg-surface-muted/60"
      data-testid={`dispositivo-row-${device.id}`}
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 font-medium text-text">
          <Smartphone className="h-4 w-4 text-text-muted" />
          <span className="min-w-0">
            <span className="block truncate">{device.nome || device.device_id}</span>
            {device.modelo && (
              <span className="block text-2xs text-text-muted">
                {device.modelo}
                {device.app_versao ? ` · v${device.app_versao}` : ""}
              </span>
            )}
          </span>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="block truncate text-text">{device.tecnico.nome}</span>
        <span className="block truncate text-2xs text-text-muted">
          {device.tecnico.email}
        </span>
      </td>
      <td className="px-4 py-3">
        {device.territorios.length === 0 ? (
          <span className="text-text-muted">—</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {device.territorios.map((t) => (
              <Chip key={t.id}>{t.nome}</Chip>
            ))}
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        {ultimo ? (
          <span title={absoluteDateTime(ultimo)}>{relativeTime(ultimo)}</span>
        ) : (
          <span className="text-text-muted">Nunca sincronizou</span>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono tabular-nums">
        {device.registros_pendentes}
      </td>
      <td className="px-4 py-3">
        <SemaforoBadge status={status} />
      </td>
    </tr>
  );
}
