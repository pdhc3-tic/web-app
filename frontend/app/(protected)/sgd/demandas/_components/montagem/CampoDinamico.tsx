"use client";

import { useQuery } from "@tanstack/react-query";
import { Input } from "@/app/components/ui/Input/Input";
import { SearchSelect, type SearchSelectOption } from "@/app/components/ui/SearchSelect/SearchSelect";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { OPCOES_SIM_NAO, type CampoSolicitacao } from "@/app/lib/camposSolicitacao";
import { formatCpfInput } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { buscarMunicipios, getMunicipio } from "@/app/lib/solicitacoes";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";

type Props = {
  campo: CampoSolicitacao;
  valor: string;
  onChange: (valor: string) => void;
  error?: string;
};

/** Sim/Não como par de rádios: os dois estados ficam à vista. */
function CampoBooleano({ campo, valor, onChange, error }: Props) {
  const nome = `campo-${campo.chave}`;
  return (
    <fieldset className="flex flex-col gap-1.5" data-testid={nome}>
      <legend className="text-sm font-medium text-text">
        {campo.rotulo}
        {campo.obrigatorio && <span className="text-error-text"> *</span>}
      </legend>
      <div className="flex gap-4">
        {OPCOES_SIM_NAO.map((op) => (
          <label key={op.value} className="flex cursor-pointer items-center gap-2 text-sm text-text">
            <input
              type="radio"
              name={nome}
              value={op.value}
              checked={valor === op.value}
              onChange={() => onChange(op.value)}
              className="accent-primary"
            />
            {op.label}
          </label>
        ))}
      </div>
      {error && <p className="text-xs text-error-text">{error}</p>}
    </fieldset>
  );
}

type Municipio = { id: number; nome: string };

/**
 * Destino da diária: busca no servidor. Numa solicitação salva só há o id, e o
 * nome vem do detalhe do município.
 */
function CampoMunicipio({ campo, valor, onChange, error }: Props) {
  const detalhe = useQuery({
    queryKey: qk.solicitacao.municipio(valor),
    queryFn: ({ signal }) => getMunicipio(valor, signal),
    enabled: !!valor,
    staleTime: Infinity,
  });

  const escolhido: SearchSelectOption<Municipio> | null =
    valor && detalhe.data ? { value: valor, label: detalhe.data.nome, item: detalhe.data } : null;

  return (
    <SearchSelect<Municipio>
      label={campo.rotulo}
      required={campo.obrigatorio}
      value={escolhido}
      onChange={(op) => onChange(op?.value ?? "")}
      search={(texto, signal) => buscarMunicipios(texto, signal)}
      queryKey={qk.solicitacao.municipios}
      placeholder="Digite o nome do município"
      emptyText="Nenhum município encontrado."
      error={error}
      data-testid={`campo-${campo.chave}`}
    />
  );
}

/** Um campo do formulário de solicitação, desenhado pelo tipo declarado em `CONFIG_POR_TIPO`. */
export function CampoDinamico(props: Props) {
  const { campo, valor, onChange, error } = props;
  const choices = useSgpChoices();
  const id = `campo-${campo.chave}`;

  switch (campo.tipo) {
    case "booleano":
      return <CampoBooleano {...props} />;
    case "municipio":
      return <CampoMunicipio {...props} />;
    case "choice":
      return (
        <Select
          id={id}
          label={campo.rotulo}
          required={campo.obrigatorio}
          options={campo.choice ? choices[campo.choice] : []}
          value={valor}
          onChange={onChange}
          helperText={campo.ajuda}
          error={error}
          name={campo.chave}
        />
      );
    case "textarea":
      return (
        <Textarea
          id={id}
          label={campo.rotulo}
          required={campo.obrigatorio}
          rows={3}
          value={valor}
          onChange={(e) => onChange(e.target.value)}
          helperText={campo.ajuda}
          error={error}
        />
      );
    default:
      return (
        <Input
          id={id}
          label={campo.rotulo}
          required={campo.obrigatorio}
          type={
            campo.tipo === "data"
              ? "date"
              : campo.tipo === "dataHora"
                ? "datetime-local"
                : campo.tipo === "inteiro"
                  ? "number"
                  : "text"
          }
          inputMode={campo.tipo === "cpf" || campo.tipo === "inteiro" ? "numeric" : undefined}
          min={campo.tipo === "inteiro" ? 1 : undefined}
          value={valor}
          onChange={(e) => onChange(campo.tipo === "cpf" ? formatCpfInput(e.target.value) : e.target.value)}
          helperText={campo.ajuda}
          error={error}
        />
      );
  }
}
