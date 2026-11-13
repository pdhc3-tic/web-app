import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Fixture da tabela de diárias (#366).
 *
 * A configuração de diárias é única no sistema: os valores com vigência
 * (`TabelaDiaria`), os municípios de cada faixa (`EnquadramentoFaixaDiaria`) e
 * os parâmetros de contagem (`SystemConfig` com prefixo `sgd_diaria_`). Gravar
 * nela muda o cálculo das diárias das outras specs, então a fixture:
 * 1. fotografa a configuração num arquivo do container (sobrevive a um run
 *    interrompido: a próxima fotografia restaura antes);
 * 2. no teardown, restaura: apaga as linhas de valor criadas depois, devolve o
 *    fim de vigência das que existiam, refaz os municípios das faixas e os
 *    parâmetros. Os parâmetros voltam por `save()`, que limpa o cache do Core.
 *
 * A trilha de auditoria das alterações fica: o AuditLog é imutável e registra o
 * que a tela fez.
 */

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const MARCADOR = "DIARIAS_366_FIXTURE";

export type DiariasFixture = {
  /** A faixa "Demais localidades", que recebe os municípios sem enquadramento. */
  faixaDemais: { id: number; nome: string };
  /** A faixa só de municípios listados (Brasília, Manaus, Rio e São Paulo). */
  faixaListada: { id: number; nome: string };
  /** O valor vigente da faixa "Demais localidades", em aberto. */
  valorDemais: { id: number; valor: string; vigenciaInicio: string };
  /** Município fora de qualquer faixa, para adicionar à faixa listada. */
  municipioLivre: { nome: string; codigoIbge: string };
};

export type ValorNoBanco = { id: number; inicio: string; fim: string | null; valor: string; origem: string };

export type EstadoDiarias = {
  valoresDemais: ValorNoBanco[];
  municipiosListada: string[];
  parametros: Record<string, string>;
};

const COMUM = `
import json, os
from django.db import transaction
from apps.core.models import Municipality, SystemConfig
from apps.sgd.models.diarias import EnquadramentoFaixaDiaria, FaixaDestinoDiaria, TabelaDiaria

FOTO = "/tmp/e2e-diarias-366.json"
demais = FaixaDestinoDiaria.objects.get(padrao="demais")
listada = FaixaDestinoDiaria.objects.filter(padrao__isnull=True).order_by("ordem", "pk").first()

def restaurar():
    if not os.path.exists(FOTO):
        return
    with open(FOTO) as f:
        foto = json.load(f)
    with transaction.atomic():
        TabelaDiaria.objects.exclude(pk__in=[v["id"] for v in foto["valores"]]).delete()
        for v in foto["valores"]:
            TabelaDiaria.objects.filter(pk=v["id"]).update(vigencia_fim=v["fim"], valor=v["valor"], origem=v["origem"])
        EnquadramentoFaixaDiaria.objects.all().delete()
        EnquadramentoFaixaDiaria.objects.bulk_create([
            EnquadramentoFaixaDiaria(faixa_id=e["faixa"], codigo_ibge=e["codigo"], nome_referencia=e["nome"])
            for e in foto["enquadramentos"]
        ])
        SystemConfig.objects.filter(chave__startswith="sgd_diaria_").exclude(chave__in=foto["parametros"]).delete()
        for chave, (valor, tipo) in foto["parametros"].items():
            config = SystemConfig.objects.filter(chave=chave).first() or SystemConfig(chave=chave)
            config.valor, config.tipo = valor, tipo
            config.save()
    os.remove(FOTO)

def fotografar():
    restaurar()
    foto = {
        "valores": [
            {"id": v.pk, "fim": v.vigencia_fim.isoformat() if v.vigencia_fim else None, "valor": str(v.valor), "origem": v.origem}
            for v in TabelaDiaria.objects.all()
        ],
        "enquadramentos": [
            {"faixa": e.faixa_id, "codigo": e.codigo_ibge, "nome": e.nome_referencia}
            for e in EnquadramentoFaixaDiaria.objects.all()
        ],
        "parametros": {
            c.chave: [c.valor, c.tipo] for c in SystemConfig.objects.filter(chave__startswith="sgd_diaria_")
        },
    }
    with open(FOTO, "w") as f:
        json.dump(foto, f)
`;

const SETUP_SCRIPT = `${COMUM}
fotografar()
valor = TabelaDiaria.objects.get(faixa_destino=demais, vigencia_fim__isnull=True)
enquadrados = EnquadramentoFaixaDiaria.objects.values_list("codigo_ibge", flat=True)
livre = Municipality.objects.exclude(codigo_ibge__in=list(enquadrados)).filter(codigo_ibge__regex=r"^\\d{7}$").order_by("nome").first()
print("${MARCADOR}_SETUP " + json.dumps({
    "faixaDemais": {"id": demais.pk, "nome": demais.nome},
    "faixaListada": {"id": listada.pk, "nome": listada.nome},
    "valorDemais": {"id": valor.pk, "valor": str(valor.valor), "vigenciaInicio": valor.vigencia_inicio.isoformat()},
    "municipioLivre": {"nome": livre.nome, "codigoIbge": livre.codigo_ibge},
}))
`;

const ESTADO_SCRIPT = `${COMUM}
print("${MARCADOR}_ESTADO " + json.dumps({
    "valoresDemais": [
        {"id": v.pk, "inicio": v.vigencia_inicio.isoformat(), "fim": v.vigencia_fim.isoformat() if v.vigencia_fim else None,
         "valor": str(v.valor), "origem": v.origem}
        for v in TabelaDiaria.objects.filter(faixa_destino=demais).order_by("vigencia_inicio")
    ],
    "municipiosListada": sorted(listada.enquadramentos.values_list("codigo_ibge", flat=True)),
    "parametros": dict(SystemConfig.objects.filter(chave__startswith="sgd_diaria_").values_list("chave", "valor")),
}))
`;

const TEARDOWN_SCRIPT = `${COMUM}
restaurar()
print("${MARCADOR}_TEARDOWN_OK")
`;

function djangoShellComoDono(script: string): string {
  return execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "backend",
      "sh",
      "-c",
      'DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD python manage.py shell -c "$1"',
      "sh",
      script,
    ],
    { cwd: REPO_ROOT, encoding: "utf8", timeout: 180_000 },
  );
}

function linhaJson<T>(saida: string, rotulo: string): T {
  const linha = saida
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith(`${MARCADOR}_${rotulo} `));
  if (!linha) throw new Error(`Fixture da #366 não devolveu ${rotulo}:\n${saida}`);
  return JSON.parse(linha.slice(`${MARCADOR}_${rotulo} `.length)) as T;
}

export function criarDiariasFixture(): DiariasFixture {
  return linhaJson<DiariasFixture>(djangoShellComoDono(SETUP_SCRIPT), "SETUP");
}

/** A configuração gravada: valores da faixa "Demais localidades", municípios da faixa listada e parâmetros. */
export function lerEstadoDiarias(): EstadoDiarias {
  return linhaJson<EstadoDiarias>(djangoShellComoDono(ESTADO_SCRIPT), "ESTADO");
}

export function removerDiariasFixture(): void {
  const saida = djangoShellComoDono(TEARDOWN_SCRIPT);
  if (!saida.includes(`${MARCADOR}_TEARDOWN_OK`)) {
    throw new Error(`Fixture da #366 não confirmou o teardown:\n${saida}`);
  }
}
