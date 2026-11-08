"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { configDoTipo, type ValoresCampos } from "@/app/lib/camposSolicitacao";
import { qk } from "@/app/lib/queryKeys";
import {
  PADRAO_SLUG,
  SCHEMA_INICIAL,
  listRubricas,
  type SchemaCampos,
  type TipoSolicitacaoCatalogo,
  type TipoSolicitacaoPayload,
} from "@/app/lib/tiposSolicitacao";
import { CampoDinamico } from "@/app/(protected)/sgd/demandas/_components/montagem/CampoDinamico";

export const AVISO_NAO_RETROAGE =
  "A alteração vale só para novas solicitações: as já criadas mantêm a rubrica e os campos.";

type Campo = "nome" | "slug" | "rubrica" | "ordem" | "schema_campos";

/** Sugestão de identificador a partir do nome: sem acento, minúsculas e hífen. */
function slugDoNome(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** O texto do editor → schema, ou a mensagem do erro de JSON. */
function lerSchema(texto: string): { schema: SchemaCampos | null; erro: string | null } {
  try {
    const valor: unknown = JSON.parse(texto);
    if (!valor || typeof valor !== "object" || Array.isArray(valor)) {
      return { schema: null, erro: "O schema precisa ser um objeto JSON." };
    }
    return { schema: valor as SchemaCampos, erro: null };
  } catch (e) {
    return { schema: null, erro: `JSON inválido: ${e instanceof Error ? e.message : String(e)}` };
  }
}

/**
 * Pré-visualização do formulário que o solicitante vai ver, desenhado pelo
 * mesmo renderizador da montagem da demanda. Num tipo de origem, mostra o
 * layout próprio, que não depende do schema.
 */
function PreviaFormulario({ slug, schema }: { slug: string; schema: SchemaCampos }) {
  const [valores, setValores] = useState<ValoresCampos>({});
  const config = configDoTipo(slug, schema);
  if (config.campos.length === 0) {
    return <p className="text-sm text-text-muted">O schema ainda não tem campos em “properties”.</p>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2" data-testid="tipo-previa">
      {config.campos
        .filter((c) => !c.visivel || c.visivel(valores))
        .map((campo) => (
          <div key={campo.chave} className={campo.largo ? "sm:col-span-2" : undefined}>
            <CampoDinamico
              campo={campo}
              valor={valores[campo.chave] ?? ""}
              onChange={(v) => setValores((atual) => ({ ...atual, [campo.chave]: v }))}
            />
          </div>
        ))}
    </div>
  );
}

/**
 * Novo e Editar um tipo do catálogo (#365). O identificador só é escolhido na
 * criação; a estratégia de validação (CPF, diárias, cotações) é dos tipos de
 * origem e aparece só para leitura. O schema é editado como JSON, com a
 * pré-visualização do formulário ao lado.
 */
export function TipoSolicitacaoForm({
  editando,
  onClose,
  onSalvar,
}: {
  /** `null` = tipo novo. */
  editando: TipoSolicitacaoCatalogo | null;
  onClose: () => void;
  onSalvar: (payload: TipoSolicitacaoPayload) => Promise<void>;
}) {
  const [nome, setNome] = useState(editando?.nome ?? "");
  const [slug, setSlug] = useState(editando?.slug ?? "");
  const [slugEditado, setSlugEditado] = useState(false);
  const [rubrica, setRubrica] = useState(editando ? String(editando.rubrica) : "");
  const [ordem, setOrdem] = useState(String(editando?.ordem ?? 0));
  const [ativo, setAtivo] = useState(editando?.ativo ?? true);
  const [textoSchema, setTextoSchema] = useState(() =>
    JSON.stringify(editando?.schema_campos ?? SCHEMA_INICIAL, null, 2),
  );
  const [erros, setErros] = useState<Partial<Record<Campo, string>>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const { schema, erro: erroJson } = useMemo(() => lerSchema(textoSchema), [textoSchema]);

  const rubricas = useQuery({
    queryKey: qk.configSgd.rubricas,
    queryFn: ({ signal }) => listRubricas(signal),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const opcoesRubrica: SelectOption[] = useMemo(() => {
    const opcoes = (rubricas.data ?? [])
      .filter((r) => r.ativo || String(r.id) === rubrica)
      .map((r) => ({ value: String(r.id), label: r.nome }));
    if (editando && !opcoes.some((o) => o.value === String(editando.rubrica))) {
      opcoes.unshift({ value: String(editando.rubrica), label: editando.rubrica_nome });
    }
    return opcoes;
  }, [rubricas.data, rubrica, editando]);

  function limparErro(campo: Campo) {
    setErros((atual) => ({ ...atual, [campo]: undefined }));
  }

  async function salvar() {
    const faltando: Partial<Record<Campo, string>> = {};
    if (!nome.trim()) faltando.nome = "Informe o nome.";
    if (!editando && !PADRAO_SLUG.test(slug)) {
      faltando.slug = "Use letras minúsculas, números e hífen, sem espaços.";
    }
    if (!rubrica) faltando.rubrica = "Escolha a rubrica.";
    if (!/^\d+$/.test(ordem.trim())) faltando.ordem = "Informe um número inteiro.";
    if (erroJson) faltando.schema_campos = erroJson;
    setErros(faltando);
    if (Object.keys(faltando).length > 0 || !schema) return;

    setSalvando(true);
    setErroGeral(null);
    try {
      await onSalvar({
        slug,
        nome: nome.trim(),
        rubrica: Number(rubrica),
        ordem: Number(ordem),
        ativo,
        schema_campos: schema,
      });
    } catch (e) {
      if (e instanceof ApiError) {
        const porCampo: Partial<Record<Campo, string>> = {};
        const soltos: string[] = [];
        for (const fe of e.fieldErrors ?? []) {
          if (["nome", "slug", "rubrica", "ordem", "schema_campos"].includes(fe.field)) {
            porCampo[fe.field as Campo] = fe.message;
          } else {
            soltos.push(fe.message);
          }
        }
        setErros(porCampo);
        if (soltos.length > 0 || Object.keys(porCampo).length === 0) {
          setErroGeral(soltos.length > 0 ? soltos.join(" ") : e.message);
        }
      } else {
        setErroGeral("Não foi possível salvar o tipo de solicitação.");
      }
    } finally {
      setSalvando(false);
    }
  }

  return (
    <SlideOver
      open
      width="wide"
      onClose={salvando ? () => {} : onClose}
      title={editando ? `Editar tipo — ${editando.nome}` : "Novo tipo de solicitação"}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={salvar} loading={salvando} data-testid="tipo-salvar">
            Salvar
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-4 py-4" data-testid="tipo-form">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            id="tipo-nome"
            label="Nome"
            required
            value={nome}
            onChange={(e) => {
              setNome(e.target.value);
              if (!editando && !slugEditado) setSlug(slugDoNome(e.target.value));
              limparErro("nome");
            }}
            error={erros.nome}
          />
          <Input
            id="tipo-slug"
            label="Identificador"
            required
            value={slug}
            disabled={!!editando}
            onChange={(e) => {
              setSlug(e.target.value.trim());
              setSlugEditado(true);
              limparErro("slug");
            }}
            helperText={editando ? "Não muda depois de criado: as solicitações o referenciam." : "Gerado pelo nome."}
            error={erros.slug}
          />
          <Select
            id="tipo-rubrica"
            label="Rubrica"
            required
            options={opcoesRubrica}
            value={rubrica}
            onChange={(v) => {
              setRubrica(v);
              limparErro("rubrica");
            }}
            placeholder={rubricas.isPending ? "Carregando rubricas…" : "Selecione a rubrica"}
            error={erros.rubrica ?? (rubricas.isError ? "Não foi possível carregar as rubricas do orçamento." : undefined)}
          />
          <Input
            id="tipo-ordem"
            label="Ordem"
            required
            type="number"
            inputMode="numeric"
            min={0}
            value={ordem}
            onChange={(e) => {
              setOrdem(e.target.value);
              limparErro("ordem");
            }}
            helperText="Posição na lista de tipos do formulário."
            error={erros.ordem}
          />
        </div>

        <label className="flex items-start gap-2 text-sm text-text">
          <input
            type="checkbox"
            checked={ativo}
            onChange={(e) => setAtivo(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-(--color-primary)"
            data-testid="tipo-ativo"
          />
          <span>
            Ativo
            <span className="block text-xs text-text-muted">
              Inativo, o tipo sai do formulário, e as solicitações que já o usam não mudam.
            </span>
          </span>
        </label>

        {editando?.validador && (
          <p className="text-sm text-text-muted" data-testid="tipo-validador">
            Validação própria: <code className="text-text">{editando.validador}</code>. As regras que o schema não
            expressa (CPF, cálculo de diárias, cotações) ficam no backend, e o formulário usa o layout de origem.
          </p>
        )}

        <Textarea
          id="tipo-schema"
          label="Campos do formulário (JSON Schema)"
          required
          rows={12}
          spellCheck={false}
          className="font-mono text-xs"
          value={textoSchema}
          onChange={(e) => {
            setTextoSchema(e.target.value);
            limparErro("schema_campos");
          }}
          helperText="Tipos aceitos: texto, número (integer/number), data (format: date), data e hora (format: date-time), booleano e enumeração (enum, ou oneOf com const e title). Use title, description, required e x-ordem para a ordem dos campos."
          error={erros.schema_campos ?? erroJson ?? undefined}
        />

        <section className="flex flex-col gap-3 rounded-md border border-border px-3 py-3">
          <h3 className="text-sm font-medium text-text">Pré-visualização</h3>
          {schema ? (
            <PreviaFormulario slug={editando?.slug ?? slug} schema={schema} />
          ) : (
            <p className="text-sm text-text-muted">Corrija o JSON para ver o formulário.</p>
          )}
        </section>

        <p className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {AVISO_NAO_RETROAGE}
        </p>

        {erroGeral && (
          <p role="alert" className="text-sm text-error-text" data-testid="tipo-erro">
            {erroGeral}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
