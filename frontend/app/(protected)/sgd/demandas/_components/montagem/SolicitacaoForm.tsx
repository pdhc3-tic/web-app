"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import {
  camposVisiveis,
  configDoTipo,
  idsDoAnexo,
  isTipoSolicitacao,
  montarCamposJson,
  validarCampos,
  valoresDoCamposJson,
  type ValoresCampos,
} from "@/app/lib/camposSolicitacao";
import { anexosDaSolicitacao, type Demanda, type SolicitacaoDemanda } from "@/app/lib/demandas";
import { formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { useTiposSolicitacao } from "@/app/lib/hooks/useTiposSolicitacao";
import { qk } from "@/app/lib/queryKeys";
import {
  atualizarSolicitacao,
  COTACOES_MINIMAS,
  criarSolicitacao,
  removerDocumentoDemanda,
  type DocumentoDemanda,
  type SolicitacaoPayload,
} from "@/app/lib/solicitacoes";
import type { ContextoAnexo } from "./CampoAnexo";
import { CampoDinamico } from "./CampoDinamico";
import { SaldoSolicitacao } from "./SaldoSolicitacao";
import { bloqueioDaDiaria, SimulacaoDiarias, useSimulacaoDiarias } from "./SimulacaoDiarias";

const CAMPO_VALOR = "valor_estimado";

/** O que decide o valor da diária: mudar um deles faz o backend recalcular ao salvar. */
const CAMPOS_DO_CALCULO_DA_DIARIA = ["municipio_destino_id", "data_inicio", "data_fim", "hospedagem_custeada"] as const;

/** Hospedagem "não" e em branco são a mesma coisa para o backend (`_parse_bool`). */
function campoDoCalculo(chave: string, valor: string | undefined): string {
  if (chave === "hospedagem_custeada") return valor === "sim" ? "sim" : "";
  return valor ?? "";
}

/**
 * Formulário de uma solicitação de recurso (#295, SGD-RF04/RF05): os campos
 * mudam com o tipo, e o saldo das duas travas aparece antes de salvar.
 *
 * Os tipos vêm do catálogo (#365): só os ativos, na ordem cadastrada. Os seis
 * de origem mantêm o layout próprio; um tipo novo é desenhado pelo schema.
 *
 * Salvar grava a solicitação na demanda (Rascunho ou Devolvida) sem reservar
 * saldo — a reserva é da submissão. Uma solicitação salva troca de tipo só
 * removendo e criando outra: o tipo define a rubrica.
 */
export function SolicitacaoForm({
  demanda,
  solicitacao,
  onClose,
  onSalvo,
}: {
  demanda: Demanda;
  /** Null: nova solicitação. */
  solicitacao: SolicitacaoDemanda | null;
  onClose: () => void;
  onSalvo: (salva: SolicitacaoDemanda, nova: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const catalogo = useTiposSolicitacao();

  const [tipo, setTipo] = useState<string>(solicitacao?.tipo ?? "");
  const tipoDoCatalogo = catalogo.data?.find((t) => t.slug === tipo);
  // O layout próprio sai na hora; o de um tipo novo espera o schema do catálogo.
  const config =
    tipo && (isTipoSolicitacao(tipo) || tipoDoCatalogo) ? configDoTipo(tipo, tipoDoCatalogo?.schema_campos) : null;

  const [valores, setValores] = useState<ValoresCampos>(() =>
    solicitacao && isTipoSolicitacao(solicitacao.tipo)
      ? valoresDoCamposJson(configDoTipo(solicitacao.tipo), solicitacao.campos_json)
      : {},
  );
  // Editando uma solicitação de tipo novo, os valores entram quando o schema chega.
  const valoresCarregados = useRef(!solicitacao || isTipoSolicitacao(solicitacao.tipo));
  useEffect(() => {
    if (valoresCarregados.current || !solicitacao || !config) return;
    valoresCarregados.current = true;
    setValores(valoresDoCamposJson(config, solicitacao.campos_json));
  }, [config, solicitacao]);
  const [valorEstimado, setValorEstimado] = useState(() =>
    solicitacao ? formatMoneyInput(solicitacao.valor_estimado) : "",
  );
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // Anexos (#365): o nome de cada documento informado, e os que subiram neste
  // formulário e ainda não foram salvos. Estes saem do backend se o usuário
  // retira o arquivo ou fecha sem salvar; sem isso, ficariam soltos na demanda e
  // ocupariam o limite de anexos ainda não informados.
  const [nomesAnexos, setNomesAnexos] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      (solicitacao ? anexosDaSolicitacao(solicitacao) : []).flatMap(([, lista]) =>
        lista.map((a) => [a.id, a.nome_original]),
      ),
    ),
  );
  const anexosNaoSalvos = useRef(new Set<number>());
  // Envios em curso seguram Salvar e a troca de tipo; um envio que termina depois
  // de o formulário fechar é apagado na chegada, sem ficar solto na demanda.
  const [enviandoAnexos, setEnviandoAnexos] = useState(0);
  const encerrado = useRef(false);

  function descartarAnexos(ids: Iterable<number>) {
    for (const docId of [...ids]) {
      anexosNaoSalvos.current.delete(docId);
      void removerDocumentoDemanda(demanda.id, docId).catch(() => {
        // Melhor esforço: o que sobrar não entra na demanda e sai se a solicitação for salva sem ele.
      });
    }
  }

  const contextoAnexo: ContextoAnexo = {
    demandaId: demanda.id,
    nomes: nomesAnexos,
    onEnviado: (doc: DocumentoDemanda) => {
      if (encerrado.current) {
        void removerDocumentoDemanda(demanda.id, doc.id).catch(() => {});
        return;
      }
      anexosNaoSalvos.current.add(doc.id);
      setNomesAnexos((prev) => ({ ...prev, [doc.id]: doc.nome_original }));
    },
    // Um anexo já salvo só sai quando a solicitação for salva sem ele (o backend remove).
    onRetirado: (docId) => {
      if (anexosNaoSalvos.current.has(docId)) descartarAnexos([docId]);
    },
    onEnviando: (ativo) => setEnviandoAnexos((n) => Math.max(0, n + (ativo ? 1 : -1))),
    bloqueado: salvando,
  };

  function fechar() {
    encerrado.current = true;
    descartarAnexos(anexosNaoSalvos.current);
    onClose();
  }

  const diarias = useSimulacaoDiarias(
    tipo === "diaria" ? (valores.municipio_destino_id ?? "") : "",
    valores.data_inicio ?? "",
    valores.data_fim ?? "",
    valores.hospedagem_custeada === "sim",
  );

  // Editar uma diária gravada sem mudar destino, datas nem hospedagem mantém o
  // valor congelado (`_congelar_diaria` no backend), mesmo sem tabela vigente.
  // Só vale para as gravadas com a tabela por faixa (`tabela_diaria_id`).
  const [valoresGravados] = useState(valores);
  const diariaCongelada =
    tipo === "diaria" &&
    solicitacao?.tipo === "diaria" &&
    !!solicitacao.campos_json?.tabela_diaria_id &&
    CAMPOS_DO_CALCULO_DA_DIARIA.every((c) => campoDoCalculo(c, valores[c]) === campoDoCalculo(c, valoresGravados[c]));
  // #440: sem valor de diária vigente (ou com outra recusa do cálculo), salvar
  // seria recusado pelo backend; o botão fica desabilitado com o motivo.
  // O motivo é lido sempre, mesmo na edição congelada: o `useQuery` só
  // redesenha o formulário pelos campos lidos aqui, e sem ler o erro o quadro
  // ficava em "Calculando…" depois que a simulação falhava.
  const motivoDaRecusa = bloqueioDaDiaria(diarias);
  const bloqueioDiaria = tipo === "diaria" && !diariaCongelada ? motivoDaRecusa : null;

  // O valor que o saldo confere: o digitado, ou, na diária, o que o backend calcula.
  const valorParaSaldo = config?.valorDigitado
    ? (moneyOrNull(valorEstimado) ?? "0")
    : (diarias.simulacao.data?.valor_total ?? solicitacao?.valor_estimado ?? "0");

  function mudarCampo(chave: string, valor: string) {
    setValores((prev) => ({ ...prev, [chave]: valor }));
    setErros((prev) => {
      const next = { ...prev };
      delete next[chave];
      return next;
    });
  }

  function mudarTipo(novo: string) {
    descartarAnexos(anexosNaoSalvos.current);
    setTipo(novo);
    setValores({});
    setErros({});
    setErroGeral(null);
  }

  async function salvar() {
    if (enviandoAnexos > 0 || bloqueioDiaria) return;
    if (!tipo || !config) {
      setErros({ tipo: "Escolha o tipo da solicitação." });
      return;
    }
    const e = validarCampos(tipo, config, valores);
    const valor = moneyOrNull(valorEstimado);
    if (config.valorDigitado && !(valor && Number(valor) > 0)) {
      e[CAMPO_VALOR] = "Informe o valor estimado.";
    }
    setErros(e);
    setErroGeral(null);
    if (Object.keys(e).length > 0) return;

    const payload: SolicitacaoPayload = { tipo, campos_json: montarCamposJson(config, valores) };
    if (config.valorDigitado && valor) payload.valor_estimado = valor;

    // Os anexos que vão de fato neste payload (só os campos visíveis entram no
    // campos_json); o que não foi nele não fica ligado à solicitação.
    const noPayload = new Set(
      camposVisiveis(config, valores)
        .filter((c) => c.tipo === "anexo")
        .flatMap((c) => idsDoAnexo(valores[c.chave] ?? "")),
    );

    setSalvando(true);
    try {
      const salva = solicitacao
        ? await atualizarSolicitacao(demanda.id, solicitacao.id, payload)
        : await criarSolicitacao(demanda.id, payload);
      // O formulário fecha: um envio que ainda chegar é apagado na chegada.
      encerrado.current = true;
      // Os do payload estão ligados à solicitação; qualquer outro ainda não
      // salvo ficaria solto na demanda, e sai.
      for (const docId of noPayload) anexosNaoSalvos.current.delete(docId);
      descartarAnexos(anexosNaoSalvos.current);
      await queryClient.invalidateQueries({ queryKey: qk.demandas.all });
      onSalvo(salva, solicitacao === null);
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setErroGeral("Não foi possível salvar a solicitação. Tente novamente.");
        return;
      }
      // Erro de um campo à vista vai para o campo; o resto, para o topo.
      const visiveis = new Set([...camposVisiveis(config, valores).map((c) => c.chave), CAMPO_VALOR]);
      const porCampo: Record<string, string> = {};
      const soltos: string[] = [];
      for (const fe of err.fieldErrors ?? []) {
        if (visiveis.has(fe.field)) porCampo[fe.field] = fe.message;
        else soltos.push(fe.message);
      }
      setErros(porCampo);
      if (soltos.length > 0 || Object.keys(porCampo).length === 0) {
        setErroGeral(soltos.length > 0 ? soltos.join(" ") : err.message);
      }
    } finally {
      setSalvando(false);
    }
  }

  const rodape = (
    <div className="flex items-center justify-end gap-2">
      {enviandoAnexos > 0 ? (
        <span className="mr-auto text-sm text-text-muted" role="status">
          Aguarde o envio do arquivo.
        </span>
      ) : (
        bloqueioDiaria && (
          <span className="mr-auto text-sm text-error-text" data-testid="solicitacao-bloqueio">
            Sem valor calculado para a diária.
          </span>
        )
      )}
      <Button variant="secondary" onClick={fechar} disabled={salvando}>
        Cancelar
      </Button>
      <Button
        onClick={salvar}
        loading={salvando}
        disabled={!tipo || enviandoAnexos > 0 || bloqueioDiaria !== null}
        data-testid="solicitacao-salvar"
      >
        Salvar solicitação
      </Button>
    </div>
  );

  return (
    <SlideOver
      open
      onClose={salvando ? () => {} : fechar}
      title={solicitacao ? `Editar solicitação — ${solicitacao.tipo_display}` : "Nova solicitação de recurso"}
      footer={rodape}
    >
      <div className="flex flex-col gap-5 px-4 py-4" data-testid="solicitacao-form">
        {!solicitacao && (
          <Select
            id="solicitacao-tipo"
            label="Tipo de solicitação"
            required
            // Trocar o tipo descarta os anexos ainda não salvos: durante o
            // salvamento, apagaria os que estão no payload a caminho do backend.
            disabled={!catalogo.data || enviandoAnexos > 0 || salvando}
            placeholder={catalogo.isPending ? "Carregando tipos…" : undefined}
            options={(catalogo.data ?? []).filter((t) => t.ativo).map((t) => ({ value: t.slug, label: t.nome }))}
            value={tipo}
            onChange={mudarTipo}
            error={erros.tipo ?? (catalogo.isError ? "Não foi possível carregar os tipos de solicitação." : undefined)}
            name="tipo"
          />
        )}

        {tipo && config && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {camposVisiveis(config, valores).map((campo) => (
                <div key={campo.chave} className={campo.largo ? "sm:col-span-2" : undefined}>
                  <CampoDinamico
                    campo={campo}
                    valor={valores[campo.chave] ?? ""}
                    onChange={(v) => mudarCampo(campo.chave, v)}
                    error={erros[campo.chave]}
                    anexo={contextoAnexo}
                  />
                </div>
              ))}
            </div>

            {config.valorDigitado ? (
              <Input
                id="solicitacao-valor"
                label="Valor estimado"
                required
                inputMode="numeric"
                value={valorEstimado}
                onChange={(ev) => {
                  setValorEstimado(formatMoneyInput(ev.target.value));
                  mudarCampo(CAMPO_VALOR, "");
                }}
                error={erros[CAMPO_VALOR]}
              />
            ) : (
              <SimulacaoDiarias {...diarias} congelada={diariaCongelada} />
            )}

            {tipo === "equipamento" && (
              <p className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text">
                <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                A submissão exige ao menos {COTACOES_MINIMAS} cotações em PDF, de fornecedores distintos.
                Anexe-as em “Documentos” na página da demanda.
              </p>
            )}

            <SaldoSolicitacao
              tipo={tipo}
              valor={valorParaSaldo}
              devolvida={demanda.status === "devolvida"}
            />
          </>
        )}

        {erroGeral && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="solicitacao-erro"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {erroGeral}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
