import { Pencil } from "lucide-react";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { Button } from "@/app/components/ui/Button/Button";
import { maskCpf } from "@/app/lib/format";
import type { UpfDetail } from "@/app/lib/upfs";

type UpfHeaderProps = {
  upf: UpfDetail;
};

/** Cabeçalho da UPF: foto + nome + CPF mascarado + chips de local/status + Editar. */
export function UpfHeader({ upf }: UpfHeaderProps) {
  const cpf = maskCpf(upf.cpf);

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <Avatar
        name={upf.nome_titular}
        src={upf.foto_url || null}
        size="lg"
        className="shadow-sm"
      />

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-2xl font-semibold tracking-tight text-text">
          {upf.nome_titular}
        </h1>
        <p className="mt-0.5 text-sm text-text-muted tabular-nums">
          {cpf || "CPF não informado"}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Chip>{upf.municipio.nome}</Chip>
          {upf.territorio && <Chip>{upf.territorio.nome}</Chip>}
          <Badge status={upf.ativa ? "ativo" : "inativo"} />
        </div>
      </div>

      <div className="shrink-0">
        <Button
          as="a"
          href={`/sgp/upfs/${upf.id}/editar/`}
          variant="secondary"
          size="sm"
          leftIcon={<Pencil className="h-4 w-4" />}
        >
          Editar
        </Button>
      </div>
    </div>
  );
}
