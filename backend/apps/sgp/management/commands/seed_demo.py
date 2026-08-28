"""
Seed de dados de DEMONSTRAÇÃO do SGP.

Diferente de `seed_core` / `seed_sgp` (dados de referência reais), este comando
popula o banco com um volume realista de dados fictícios para exercitar as telas
do frontend: municípios, comunidades, UPFs com famílias, produções, plano de
trabalho, atividades e evidências (fotos/documentos). Inclui também o cenário
do SCA (#193): técnicos com dispositivos nas faixas verde/laranja/vermelha,
histórico de eventos de sincronização, conflitos (pendente sensível e resolvido)
e registros com origem "sca" para os badges.

NÃO usar em produção nem em testes automatizados (para testes, usar as factories
em apps/sgp/tests/factories.py).

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --reset      # apaga o seed anterior e recria
    python manage.py seed_demo --no-files   # não gera arquivos de evidência
"""

from __future__ import annotations

import os
import random
import struct
import zlib
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.models import Municipality, Organization, Role, State, SystemConfig, Territory, UserProfile
from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sgp.models import (
    Activity,
    ActivityDocument,
    ActivityPhoto,
    Comunidade,
    Cultura,
    EspecieAnimal,
    MembroFamilia,
    Production,
    Projeto,
    UPF,
    UPFDocument,
    WorkPlanAcao,
    WorkPlanMeta,
)

User = get_user_model()

SEED = 20260808
DEMO_EMAIL_DOMAIN = "demo.pdhc.local"
DEMO_PASSWORD = "Pdhc@2026demo"
# URL que o NAVEGADOR usa para baixar as evidências. Depende da porta em que o
# backend está publicado no host (docker-compose), por isso é configurável.
MEDIA_BASE_URL = os.getenv("DEMO_MEDIA_BASE_URL", "http://localhost:8000/media")


# ───────────────────────────────────────────────────────────────────────────────
# Dados de apoio
# ───────────────────────────────────────────────────────────────────────────────

# (codigo_ibge, nome, sigla_estado, lat, lng)
MUNICIPIOS = [
    ("2613909", "Serra Talhada", "PE", -7.992, -38.297),
    ("2611101", "Petrolina", "PE", -9.389, -40.502),
    ("2601201", "Arcoverde", "PE", -8.419, -37.054),
    ("2516003", "Sousa", "PB", -6.759, -38.231),
    ("2510808", "Patos", "PB", -7.024, -37.280),
    ("2503704", "Cajazeiras", "PB", -6.890, -38.561),
    ("2702405", "Delmiro Gouveia", "AL", -9.388, -37.996),
    ("2707701", "Santana do Ipanema", "AL", -9.378, -37.245),
    ("2700300", "Arapiraca", "AL", -9.752, -36.661),
    ("2408102", "Mossoró", "RN", -5.187, -37.344),
    ("2402006", "Caicó", "RN", -6.458, -37.098),
    ("2400703", "Apodi", "RN", -5.664, -37.799),
    ("2101202", "Balsas", "MA", -7.532, -46.035),
    ("2103000", "Codó", "MA", -4.455, -43.885),
    ("2101400", "Barra do Corda", "MA", -5.505, -45.243),
    ("2918407", "Juazeiro", "BA", -9.416, -40.503),
    ("2913606", "Irecê", "BA", -11.304, -41.856),
    ("2911709", "Guanambi", "BA", -14.223, -42.781),
    ("3135803", "Januária", "MG", -15.487, -44.362),
    ("3143302", "Montes Claros", "MG", -16.735, -43.862),
    ("3157203", "Salinas", "MG", -16.171, -42.292),
]

COMUNIDADE_PREFIXOS = [
    "Sítio", "Assentamento", "Povoado", "Comunidade", "Fazenda", "Serra do",
]
COMUNIDADE_NOMES = [
    "Malhada Grande", "Nova Esperança", "Riacho Fundo", "Boa Vista",
    "Lagoa do Meio", "Várzea Comprida", "Santa Luzia", "Olho d'Água",
    "Barra Nova", "Pedra Branca", "Baixio Verde", "Recanto Feliz",
]

NOMES_M = [
    "José", "Antônio", "Francisco", "João", "Severino", "Manoel", "Raimundo",
    "Sebastião", "Pedro", "Luiz", "Geraldo", "Djalma", "Cícero", "Expedito",
]
NOMES_F = [
    "Maria", "Ana", "Francisca", "Josefa", "Antônia", "Rita", "Terezinha",
    "Luzia", "Severina", "Raimunda", "Joana", "Damiana", "Cícera", "Benedita",
]
SOBRENOMES = [
    "da Silva", "dos Santos", "de Oliveira", "Ferreira", "Alves", "Pereira",
    "Lima", "Gomes", "Ribeiro", "Barbosa", "Nunes", "Rocha", "Bezerra",
    "Cavalcante", "Feitosa", "Marinho", "Vieira", "Sampaio",
]

SEGURIDADE = [
    "Aposentadoria", "BPC/LOAS", "Bolsa Família", "Auxílio Brasil",
    "Pensão", "Seguro-defeso", "Nenhum", "Outros",
]
SAUDE = [
    "diabetes", "hipertensao", "deficiencia_visual", "doenca_cardiaca",
    "gestante", "lactante", "doenca_cronica", "alergia_alimentar",
]

ORGANIZACOES = [
    ("Associação dos Agricultores de Serra Talhada", "ASSOCIACAO"),
    ("Cooperativa Agrofamiliar do Sertão", "COOPERATIVA"),
    ("Sindicato dos Trabalhadores Rurais de Sousa", "ASSOCIACAO"),
    ("Fundação Semiárido Vivo", "FUNDACAO"),
    ("Cooperativa Mista do Vale do São Francisco", "COOPERATIVA"),
    ("Associação Comunitária de Caicó", "ASSOCIACAO"),
    ("Rede de Sementes Crioulas do Norte de Minas", "OUTRO"),
    ("Cooperativa dos Apicultores de Irecê", "COOPERATIVA"),
]

# (numero, titulo, [ods], [(numero_acao, descricao, tipo_unidade, qtd, valor)])
METAS = [
    (1, "Fortalecimento da organização produtiva das famílias", [1, 2, 8], [
        ("1.1", "Realizar oficinas de organização produtiva", 2, 40, 3500),
        ("1.2", "Realizar cursos de capacitação em gestão", 3, 24, 6800),
        ("1.3", "Promover intercâmbios entre comunidades", 6, 12, 12000),
    ]),
    (2, "Assistência técnica e extensão rural continuada", [2, 8], [
        ("2.1", "Realizar visitas técnicas às UPFs", 8, 600, 320),
        ("2.2", "Elaborar planos de desenvolvimento familiar", 4, 300, 450),
        ("2.3", "Atender famílias com ATER continuada", 11, 300, 1200),
    ]),
    (3, "Acesso à água para consumo e produção", [6, 13], [
        ("3.1", "Implantar cisternas de consumo", 10, 180, 5200),
        ("3.2", "Implantar sistemas de irrigação de baixo custo", 10, 60, 9800),
    ]),
    (4, "Convivência com o semiárido e agroecologia", [2, 13, 15], [
        ("4.1", "Realizar dias de campo em unidades demonstrativas", 9, 30, 2800),
        ("4.2", "Implantar quintais produtivos agroecológicos", 10, 120, 3100),
        ("4.3", "Realizar seminários de agroecologia", 1, 8, 18000),
    ]),
    (5, "Inclusão produtiva de mulheres e juventude rural", [5, 8, 10], [
        ("5.1", "Realizar oficinas com grupos de mulheres", 2, 36, 3400),
        ("5.2", "Realizar encontros da juventude rural", 9, 14, 7600),
    ]),
    (6, "Acesso a mercados e comercialização", [1, 8, 12], [
        ("6.1", "Apoiar acesso ao PNAE e PAA", 4, 90, 900),
        ("6.2", "Realizar feiras da agricultura familiar", 9, 18, 5500),
    ]),
    (7, "Monitoramento, avaliação e gestão do conhecimento", [16, 17], [
        ("7.1", "Produzir relatórios de pesquisa e sistematização", 5, 12, 8200),
        ("7.2", "Produzir conteúdos audiovisuais", 7, 24, 2400),
    ]),
]

TIPOS_ATIVIDADE = [
    "visita_tecnica", "reuniao_comunitaria", "oficina", "intercambio",
    "curso_capacitacao", "dia_de_campo", "seminario", "encontro",
    "dia_de_partilha", "ater", "pesquisa_de_campo",
]

TITULOS_ATIVIDADE = {
    "visita_tecnica": "Visita técnica à UPF — acompanhamento produtivo",
    "reuniao_comunitaria": "Reunião comunitária de mobilização",
    "oficina": "Oficina de manejo agroecológico do solo",
    "intercambio": "Intercâmbio entre famílias agricultoras",
    "curso_capacitacao": "Curso de capacitação em gestão da produção",
    "dia_de_campo": "Dia de campo em unidade demonstrativa",
    "seminario": "Seminário territorial de convivência com o semiárido",
    "encontro": "Encontro de articulação territorial",
    "dia_de_partilha": "Dia de partilha de sementes crioulas",
    "ater": "Atendimento de ATER continuada",
    "pesquisa_de_campo": "Pesquisa de campo — diagnóstico produtivo",
}

# técnicos: (primeiro nome, sobrenome, slug do perfil)
TECNICOS = [
    ("Marina", "Albuquerque", "adt-acr"),
    ("Rodrigo", "Tavares", "adt-acr"),
    ("Cláudia", "Meneses", "adt-acr"),
    ("Ewerton", "Bandeira", "adt-acr"),
    ("Sandra", "Queiroz", "articulador-estadual"),
    ("Hélio", "Fontenele", "articulador-estadual"),
    ("Beatriz", "Nogueira", "ugp"),
    ("Adriano", "Peixoto", "fgd"),
]


# ───────────────────────────────────────────────────────────────────────────────
# Geradores de documento (CPF/CNPJ com dígitos verificadores válidos)
# ───────────────────────────────────────────────────────────────────────────────

def gerar_cpf(rnd: random.Random) -> str:
    base = [rnd.randint(0, 9) for _ in range(9)]
    for pesos in (range(10, 1, -1), range(11, 1, -1)):
        soma = sum(d * p for d, p in zip(base, pesos))
        resto = soma % 11
        base.append(0 if resto < 2 else 11 - resto)
    return "".join(str(d) for d in base)


def gerar_cnpj(rnd: random.Random) -> str:
    base = [rnd.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        soma = sum(d * p for d, p in zip(base, pesos))
        resto = soma % 11
        base.append(0 if resto < 2 else 11 - resto)
    s = "".join(str(d) for d in base)
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


# ───────────────────────────────────────────────────────────────────────────────
# Geradores de arquivo (PNG e PDF válidos, sem dependências externas)
# ───────────────────────────────────────────────────────────────────────────────

def _png(width: int, height: int, topo: tuple, base: tuple) -> bytes:
    """PNG RGB simples: faixa superior sólida + gradiente horizontal abaixo."""
    linha_topo = b"\x00" + bytes(bytearray(
        c for x in range(width) for c in topo
    ))
    linha_base = b"\x00" + bytes(bytearray(
        c
        for x in range(width)
        for c in (
            int(base[0] + (topo[0] - base[0]) * x / width),
            int(base[1] + (topo[1] - base[1]) * x / width),
            base[2],
        )
    ))
    corte = height // 3
    raw = linha_topo * corte + linha_base * (height - corte)

    def chunk(tipo: bytes, dados: bytes) -> bytes:
        return (
            struct.pack(">I", len(dados))
            + tipo
            + dados
            + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def _pdf(titulo: str, linhas: list[str]) -> bytes:
    """PDF 1.4 de uma página, fonte Helvetica, sem dependências."""
    conteudo = ["BT", "/F1 16 Tf", "72 780 Td", f"({_esc(titulo)}) Tj", "/F1 11 Tf"]
    for linha in linhas:
        conteudo += ["0 -22 Td", f"({_esc(linha)}) Tj"]
    conteudo.append("ET")
    stream = "\n".join(conteudo).encode("latin-1", "replace")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    inicio_xref = len(out)
    out += f"xref\n0 {len(objetos) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _esc(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


# ───────────────────────────────────────────────────────────────────────────────
# Command
# ───────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração do SGP (UPFs, famílias, atividades…)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Apaga os dados de demonstração existentes antes de recriar.",
        )
        parser.add_argument(
            "--no-files", action="store_true",
            help="Não gera os arquivos de evidência (fotos/documentos) em MEDIA_ROOT.",
        )
        parser.add_argument(
            "--upfs", type=int, default=40, help="Quantidade de UPFs (padrão: 40).",
        )
        parser.add_argument(
            "--atividades", type=int, default=45,
            help="Quantidade de atividades (padrão: 45).",
        )

    def handle(self, *args, **options):
        self.rnd = random.Random(SEED)
        self.gerar_arquivos = not options["no_files"]
        self.media_root = Path(settings.MEDIA_ROOT)

        if options["reset"]:
            self._reset()

        if UPF.objects.exists():
            self.stdout.write(self.style.WARNING(
                "Já existem UPFs no banco. Rode com --reset para recriar do zero."
            ))
            return

        with transaction.atomic():
            projeto = self._projeto()
            tecnicos = self._tecnicos()
            municipios = self._municipios()
            self._organizacoes(municipios)
            comunidades = self._comunidades(municipios, tecnicos[0])
            upfs = self._upfs(projeto, comunidades, tecnicos, options["upfs"])
            self._producoes(upfs)
            acoes = self._plano_trabalho(tecnicos[-2])
            self._atividades(acoes, comunidades, upfs, tecnicos, options["atividades"])
            self._sca(tecnicos, upfs)

        self._resumo()

    # ── Reset ──────────────────────────────────────────────────────────────────

    def _reset(self):
        self.stdout.write("Removendo dados de demonstração anteriores...")

        if self.gerar_arquivos:
            chaves = list(ActivityPhoto.objects.values_list("arquivo_key", flat=True))
            chaves += list(ActivityDocument.objects.values_list("arquivo_key", flat=True))
            chaves += list(UPFDocument.objects.values_list("arquivo_key", flat=True))
            for chave in chaves:
                caminho = self.media_root / chave
                if caminho.is_file():
                    caminho.unlink()

        with transaction.atomic():
            ActivityPhoto.objects.all().delete()
            ActivityDocument.objects.all().delete()
            Activity.objects.all().delete()
            WorkPlanAcao.objects.all().delete()
            WorkPlanMeta.objects.all().delete()
            Production.objects.all().delete()
            UPFDocument.objects.all().delete()
            # ciclo de exclusão: UPF.titular é PROTECT e Membro.upf é CASCADE —
            # desligar os membros das UPFs antes de apagar destrava as duas pontas
            MembroFamilia.objects.update(upf=None)
            UPF.objects.all().delete()
            MembroFamilia.objects.all().delete()
            Comunidade.objects.all().delete()
            Organization.objects.all().delete()
            # SCA: eventos/conflitos referenciam usuários e dispositivos (SET_NULL)
            SyncEvent.objects.all().delete()
            ConflictLog.objects.all().delete()
            SyncDevice.objects.all().delete()
            UserProfile.objects.filter(
                user__email__endswith=f"@{DEMO_EMAIL_DOMAIN}"
            ).delete()
            User.objects.filter(email__endswith=f"@{DEMO_EMAIL_DOMAIN}").delete()

    # ── Blocos de seed ─────────────────────────────────────────────────────────

    def _projeto(self) -> Projeto:
        projeto, _ = Projeto.objects.get_or_create(
            nome="Projeto Dom Hélder Câmara III",
            defaults={"descricao": "Projeto PDHC III", "ativo": True},
        )
        self.stdout.write(f"Projeto: {projeto.nome}")
        return projeto

    def _tecnicos(self) -> list:
        usuarios = []
        for primeiro, ultimo, slug in TECNICOS:
            email = f"{primeiro}.{ultimo}@{DEMO_EMAIL_DOMAIN}".lower()
            email = email.replace("á", "a").replace("é", "e").replace("í", "i")
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    nome=f"{primeiro} {ultimo}",
                    password=DEMO_PASSWORD,
                )
            role = Role.objects.get(slug=slug)
            territorio = None
            if slug == "adt-acr":
                territorio = self.rnd.choice(list(Territory.objects.all()))
            UserProfile.objects.get_or_create(
                user=user, perfil=role, territorio=territorio,
            )
            usuarios.append(user)
        self.stdout.write(f"Técnicos: {len(usuarios)} usuários (senha: {DEMO_PASSWORD})")
        return usuarios

    def _municipios(self) -> list:
        criados = []
        for codigo, nome, sigla, lat, lng in MUNICIPIOS:
            state = State.objects.get(sigla=sigla)
            territorio = Territory.objects.filter(estados__contains=[sigla]).first()
            municipio, _ = Municipality.objects.get_or_create(
                codigo_ibge=codigo,
                defaults={"nome": nome, "state": state, "territory": territorio},
            )
            municipio._coord = (lat, lng)
            criados.append(municipio)
        self.stdout.write(f"Municípios: {len(criados)}")
        return criados

    def _organizacoes(self, municipios: list):
        for nome, tipo in ORGANIZACOES:
            municipio = self.rnd.choice(municipios)
            org, criada = Organization.objects.get_or_create(
                nome=nome,
                defaults={
                    "cnpj": gerar_cnpj(self.rnd),
                    "tipo": tipo,
                    "municipio": municipio,
                    "contato": f"{self.rnd.choice(NOMES_F)} {self.rnd.choice(SOBRENOMES)}",
                    "email": f"contato@{nome.split()[0].lower()}.org.br",
                    "telefone": self._telefone(),
                },
            )
            if criada and municipio.territory:
                org.territorios.add(municipio.territory)
        self.stdout.write(f"Organizações: {Organization.objects.count()}")

    def _comunidades(self, municipios: list, criador) -> list:
        comunidades = []
        nomes = COMUNIDADE_NOMES[:]
        for municipio in municipios:
            self.rnd.shuffle(nomes)
            for nome_base in nomes[:2]:
                nome = f"{self.rnd.choice(COMUNIDADE_PREFIXOS)} {nome_base}"
                lat, lng = municipio._coord
                comunidade, _ = Comunidade.objects.get_or_create(
                    nome=nome,
                    municipio=municipio,
                    defaults={
                        "lat": Decimal(str(round(lat + self.rnd.uniform(-0.12, 0.12), 6))),
                        "lng": Decimal(str(round(lng + self.rnd.uniform(-0.12, 0.12), 6))),
                        "criada_por": criador,
                    },
                )
                comunidades.append(comunidade)
        self.stdout.write(f"Comunidades: {len(comunidades)}")
        return comunidades

    def _upfs(self, projeto, comunidades, tecnicos, quantidade) -> list:
        upfs = []
        for i in range(quantidade):
            comunidade = comunidades[i % len(comunidades)]
            municipio = comunidade.municipio
            criador = self.rnd.choice(tecnicos)

            titular = self._membro(grau_parentesco="titular", criador=criador, idade=(30, 68))
            upf = UPF.objects.create(
                projeto=projeto,
                comunidade=comunidade,
                titular=titular,
                apelido=self.rnd.choice(["", "", f"Sítio do {titular.nome_completo.split()[0]}"]),
                whatsapp=self._telefone(),
                celular=self._telefone(),
                internet=self.rnd.random() < 0.55,
                dispositivo=self.rnd.choice([1, 3, 4, 4, 4, 5]),
                cep=f"{self.rnd.randint(50000, 59999)}{self.rnd.randint(100, 999)}",
                logradouro=f"Estrada Vicinal km {self.rnd.randint(2, 40)}",
                numero=str(self.rnd.randint(1, 400)),
                bairro="Zona Rural",
                municipio=municipio,
                territorio=municipio.territory,
                latitude=Decimal(str(round(float(comunidade.lat) + self.rnd.uniform(-0.05, 0.05), 6))),
                longitude=Decimal(str(round(float(comunidade.lng) + self.rnd.uniform(-0.05, 0.05), 6))),
                pct=self.rnd.choice([1, 2, 2, 2, 3]),
                posse_terra=self.rnd.choice([1, 1, 2, 3, 4, 5]),
                area_terra_ha=Decimal(str(round(self.rnd.uniform(0.8, 42.0), 2))),
                situacao_moradia=self.rnd.choice([1, 1, 1, 2, 3]),
                tipo_moradia=self.rnd.choice([1, 1, 1, 3, 4]),
                material_construcao=self.rnd.choice([1, 1, 2, 3, 5]),
                num_comodos=self.rnd.randint(2, 8),
                energia=self.rnd.choice([1, 1, 1, 2]),
                agua=self.rnd.choice([1, 2, 3, 4, 5, 6]),
                numero_dap=f"DAP{self.rnd.randint(100000, 999999)}",
                nis=str(self.rnd.randint(10000000000, 99999999999)),
                seguridade_social=self.rnd.sample(SEGURIDADE, self.rnd.randint(0, 2)),
                criado_por=criador,
                ativa=self.rnd.random() < 0.94,
            )

            titular.upf = upf
            titular.save(update_fields=["upf"])

            # cônjuge + filhos + eventual agregado
            composicao = ["conjuge"] if self.rnd.random() < 0.75 else []
            composicao += ["filho"] * self.rnd.randint(0, 4)
            if self.rnd.random() < 0.2:
                composicao.append(self.rnd.choice(["mae", "pai", "neto", "irmao"]))
            for parentesco in composicao:
                faixa = (0, 21) if parentesco in ("filho", "neto") else (25, 82)
                self._membro(grau_parentesco=parentesco, criador=criador, idade=faixa, upf=upf)

            upfs.append(upf)

        self.stdout.write(
            f"UPFs: {len(upfs)} | Membros: {MembroFamilia.objects.count()}"
        )
        self._documentos_upf(upfs)
        return upfs

    def _membro(self, grau_parentesco, criador, idade, upf=None) -> MembroFamilia:
        genero = self.rnd.choice([1, 2])
        primeiro = self.rnd.choice(NOMES_M if genero == 1 else NOMES_F)
        nome = f"{primeiro} {self.rnd.choice(SOBRENOMES)} {self.rnd.choice(SOBRENOMES)}"
        anos = self.rnd.randint(*idade)
        nascimento = date.today() - timedelta(days=anos * 365 + self.rnd.randint(0, 364))
        menor = anos < 18
        return MembroFamilia.objects.create(
            upf=upf,
            nome_completo=nome,
            data_nascimento=nascimento,
            genero=genero,
            cor_raca=self.rnd.choice([2, 3, 3, 3, 1, 5]),
            cpf="" if anos < 12 else gerar_cpf(self.rnd),
            rg="" if menor else str(self.rnd.randint(1000000, 9999999)),
            nis=str(self.rnd.randint(10000000000, 99999999999)),
            caf=f"CAF{self.rnd.randint(100000, 999999)}" if grau_parentesco == "titular" else "",
            grau_parentesco=grau_parentesco,
            escola="Escola Municipal Rural" if menor and anos >= 5 else "",
            escolaridade=self.rnd.choice([1, 2, 2, 3, 4, 5]) if not menor else self.rnd.choice([1, 2]),
            seguridade_social=self.rnd.sample(SEGURIDADE, self.rnd.randint(0, 2)),
            saude=self.rnd.sample(SAUDE, self.rnd.randint(0, 2)),
            criado_por=criador,
        )

    def _documentos_upf(self, upfs: list):
        total = 0
        for upf in upfs:
            if self.rnd.random() > 0.4:
                continue
            tipo = self.rnd.choice(["dap_caf", "contrato", "laudo", "identidade"])
            nome_original = f"{tipo}_{upf.titular.nome_completo.split()[0].lower()}.pdf"
            chave = f"upfs/{upf.pk}/documentos/{uuid4()}.pdf"
            conteudo = _pdf(
                f"Documento — {tipo.upper()}",
                [
                    f"UPF #{upf.pk} — titular: {upf.titular.nome_completo}",
                    f"Municipio: {upf.municipio.nome}/{upf.municipio.state.sigla}",
                    f"Comunidade: {upf.comunidade.nome if upf.comunidade else '-'}",
                    "",
                    "Documento ficticio gerado por seed_demo para testes de interface.",
                ],
            )
            tamanho = self._escrever(chave, conteudo)
            UPFDocument.objects.create(
                upf=upf,
                tipo=tipo,
                descricao=f"{tipo.replace('_', '/').upper()} do titular",
                arquivo_key=chave,
                nome_original=nome_original,
                content_type="application/pdf",
                tamanho_bytes=tamanho,
                data_documento=date.today() - timedelta(days=self.rnd.randint(30, 900)),
                criado_por=upf.criado_por,
            )
            total += 1
        self.stdout.write(f"Documentos de UPF: {total}")

    def _producoes(self, upfs: list):
        culturas = list(Cultura.objects.filter(ativa=True))
        especies = list(EspecieAnimal.objects.all())
        total = 0
        for upf in upfs:
            for _ in range(self.rnd.randint(1, 3)):
                tipo = self.rnd.choices(
                    ["agricola", "pecuaria", "outra"], weights=[5, 4, 2]
                )[0]
                campos = dict(
                    upf=upf,
                    tipo=tipo,
                    custo_anual=Decimal(str(round(self.rnd.uniform(400, 9000), 2))),
                    observacoes="",
                )
                if tipo == "agricola":
                    campos.update(
                        cultura=self.rnd.choice(culturas),
                        area_ha=Decimal(str(round(self.rnd.uniform(0.2, 8.0), 2))),
                        producao_estimada=Decimal(str(round(self.rnd.uniform(50, 4000), 2))),
                        unidade_producao=self.rnd.choice(["kg", "sacas", "t", "unidades"]),
                        sementes_crioulas=self.rnd.random() < 0.45,
                    )
                elif tipo == "pecuaria":
                    campos.update(
                        especie=self.rnd.choice(especies),
                        n_matrizes=self.rnd.randint(1, 40),
                        n_reprodutores=self.rnd.randint(0, 4),
                        n_jovens=self.rnd.randint(0, 30),
                        area_pastejo_ha=Decimal(str(round(self.rnd.uniform(0.5, 25.0), 2))),
                        sistema_criacao=self.rnd.choice(
                            ["extensivo", "semi_intensivo", "intensivo"]
                        ),
                    )
                else:
                    campos.update(
                        tipo_outra=self.rnd.choice(
                            ["artesanato", "beneficiamento", "extrativismo", "outro"]
                        ),
                        descricao_outra=self.rnd.choice([
                            "Produção de doces e polpas de frutas",
                            "Artesanato em palha de carnaúba",
                            "Beneficiamento de mel e derivados",
                            "Extrativismo de babaçu",
                        ]),
                        quantidade_produzida=f"{self.rnd.randint(10, 400)} unidades/mês",
                        renda_estimada_mensal=Decimal(str(round(self.rnd.uniform(150, 2200), 2))),
                    )
                Production.objects.create(**campos)
                total += 1
        self.stdout.write(f"Produções: {total}")

    def _plano_trabalho(self, criador) -> list:
        acoes = []
        inicio = date(2025, 1, 1)
        fim = date(2027, 12, 31)
        for numero, titulo, ods, lista_acoes in METAS:
            meta, _ = WorkPlanMeta.objects.get_or_create(
                numero=numero,
                defaults={
                    "titulo": titulo,
                    "descricao": f"Meta {numero} do Plano de Trabalho do PDHC III.",
                    "ods_ids": ods,
                    "data_inicio": inicio,
                    "data_fim": fim,
                    "criado_por": criador,
                },
            )
            for num_acao, descricao, unidade, qtd, valor in lista_acoes:
                acao, _ = WorkPlanAcao.objects.get_or_create(
                    meta=meta,
                    numero=num_acao,
                    defaults={
                        "descricao": descricao,
                        "tipo_unidade": unidade,
                        "quantidade_planejada": Decimal(qtd),
                        "valor_unitario": Decimal(valor),
                        "data_inicio": inicio,
                        "data_fim": fim,
                    },
                )
                acoes.append(acao)
        self.stdout.write(
            f"Plano de Trabalho: {WorkPlanMeta.objects.count()} metas, {len(acoes)} ações"
        )
        return acoes

    def _atividades(self, acoes, comunidades, upfs, tecnicos, quantidade):
        hoje = timezone.localdate()
        tz = timezone.get_current_timezone()
        # distribuição de status coerente com a linha do tempo
        passado = [
            "concluido", "concluido", "concluido", "concluido",
            "concluido_sem_evidencia", "nao_realizada", "cancelada", "adiada",
        ]
        futuro = ["planejado", "planejado", "agendado", "agendado"]

        criadas = 0
        for i in range(quantidade):
            dias = self.rnd.randint(-180, 60)
            data = hoje + timedelta(days=dias)
            if dias < -1:
                status = self.rnd.choice(passado)
            elif dias <= 2:
                status = self.rnd.choice(["em_andamento", "agendado"])
            else:
                status = self.rnd.choice(futuro)

            comunidade = self.rnd.choice(comunidades)
            municipio = comunidade.municipio
            tipo = self.rnd.choice(TIPOS_ATIVIDADE)
            hora_inicio = self.rnd.choice([8, 9, 13, 14])
            inicio = timezone.make_aware(
                datetime.combine(data, time(hora_inicio, 0)), tz
            )
            fim = inicio + timedelta(hours=self.rnd.randint(2, 7))

            justificativa = ""
            if status == "nao_realizada":
                justificativa = "Atividade não realizada por baixa adesão das famílias na data prevista."
            elif status == "cancelada":
                justificativa = "Cancelada por indisponibilidade de transporte da equipe técnica."
            elif status == "adiada":
                justificativa = "Adiada em função de chuvas intensas na região."

            atividade = Activity.objects.create(
                titulo=f"{TITULOS_ATIVIDADE[tipo]} — {comunidade.nome}",
                tipo_atividade=tipo,
                acao=self.rnd.choice(acoes),
                forma_atuacao=self.rnd.choice(
                    ["realizacao", "realizacao", "participacao", "apoio", "articulacao"]
                ),
                tecnico_responsavel=self.rnd.choice(tecnicos),
                municipio=municipio,
                comunidade=comunidade,
                ambito=self.rnd.choice(
                    ["municipal", "municipal", "microrregional", "estadual", "supraestadual"]
                ),
                latitude=comunidade.lat,
                longitude=comunidade.lng,
                data_inicio=inicio,
                data_fim=fim,
                parceiros=self.rnd.choice([
                    "", "", "Sindicato dos Trabalhadores Rurais",
                    "Prefeitura Municipal; EMATER", "Cooperativa local; Escola Família Agrícola",
                ]),
                descricao_narrativa=(
                    f"{TITULOS_ATIVIDADE[tipo]} realizada na comunidade {comunidade.nome}, "
                    f"município de {municipio.nome}/{municipio.state.sigla}. "
                    "Trabalho conduzido com metodologia participativa, com foco na troca de "
                    "saberes entre as famílias agricultoras e a equipe técnica."
                ),
                resultados_alcancados=(
                    "Famílias mobilizadas e encaminhamentos registrados em ata."
                    if status.startswith("concluido") else ""
                ),
                status=status,
                justificativa=justificativa,
                criado_por=self.rnd.choice(tecnicos),
            )

            equipe = self.rnd.sample(tecnicos, self.rnd.randint(0, 2))
            atividade.equipe_adicional.set(
                [u for u in equipe if u != atividade.tecnico_responsavel]
            )

            upfs_municipio = [u for u in upfs if u.municipio_id == municipio.pk] or upfs
            participantes = self.rnd.sample(
                upfs_municipio, min(len(upfs_municipio), self.rnd.randint(1, 6))
            )
            atividade.upfs_participantes.set(participantes)
            membros = [
                m
                for upf in participantes
                for m in upf.membros.all()
                if self.rnd.random() < 0.5
            ]
            atividade.membros_participantes.set(membros)

            if status == "concluido":
                self._evidencias(atividade)

            criadas += 1

        self.stdout.write(
            f"Atividades: {criadas} "
            f"(fotos: {ActivityPhoto.objects.count()}, "
            f"documentos: {ActivityDocument.objects.count()})"
        )

    def _evidencias(self, atividade: Activity):
        paletas = [
            ((132, 168, 96), (214, 199, 148)),   # roçado
            ((96, 140, 176), (206, 214, 196)),   # céu / caatinga
            ((176, 132, 84), (222, 206, 172)),   # solo
            ((108, 152, 120), (198, 210, 176)),  # quintal produtivo
        ]
        for ordem in range(self.rnd.randint(2, 4)):
            topo, base = self.rnd.choice(paletas)
            chave = f"atividades/{atividade.pk}/fotos/{uuid4()}.png"
            tamanho = self._escrever(chave, _png(480, 320, topo, base))
            ActivityPhoto.objects.create(
                activity=atividade,
                arquivo_key=chave,
                arquivo_url=f"{MEDIA_BASE_URL}/{chave}",
                legenda=self.rnd.choice([
                    "Registro da atividade em campo",
                    "Participantes durante a dinâmica",
                    "Unidade demonstrativa visitada",
                    "Equipe técnica com as famílias",
                    "",
                ]),
                data_hora_captura=atividade.data_inicio + timedelta(
                    minutes=self.rnd.randint(10, 240)
                ),
                latitude=atividade.latitude,
                longitude=atividade.longitude,
                ordem=ordem,
                content_type="image/png",
                tamanho_bytes=tamanho,
                criado_por=atividade.tecnico_responsavel,
            )

        for _ in range(self.rnd.randint(1, 2)):
            tipo = self.rnd.choice(["lista_presenca", "ata", "relatorio_parcial"])
            chave = f"atividades/{atividade.pk}/documentos/{uuid4()}.pdf"
            conteudo = _pdf(
                f"{tipo.replace('_', ' ').title()} — Atividade #{atividade.pk}",
                [
                    atividade.titulo[:80],
                    f"Data: {atividade.data_inicio.strftime('%d/%m/%Y')}",
                    f"Municipio: {atividade.municipio.nome}",
                    f"Responsavel: {atividade.tecnico_responsavel.nome}",
                    "",
                    "Documento ficticio gerado por seed_demo para testes de interface.",
                ],
            )
            tamanho = self._escrever(chave, conteudo)
            ActivityDocument.objects.create(
                activity=atividade,
                arquivo_key=chave,
                arquivo_url=f"{MEDIA_BASE_URL}/{chave}",
                tipo=tipo,
                descricao=f"{tipo.replace('_', ' ')} da atividade",
                nome_original=f"{tipo}_{atividade.pk}.pdf",
                content_type="application/pdf",
                tamanho_bytes=tamanho,
                data_documento=atividade.data_inicio.date(),
                criado_por=atividade.tecnico_responsavel,
            )

    # ── Utilitários ────────────────────────────────────────────────────────────

    def _escrever(self, chave: str, conteudo: bytes) -> int:
        if not self.gerar_arquivos:
            return len(conteudo)
        caminho = self.media_root / chave
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return len(conteudo)

    def _telefone(self) -> str:
        return f"({self.rnd.randint(81, 89)}) 9{self.rnd.randint(1000, 9999)}-{self.rnd.randint(1000, 9999)}"

    # ── Bloco SCA (#193) ──────────────────────────────────────────────────────

    SCA_TECNICOS = [
        ("sca.verde", "Técnico SCA Verde"),
        ("sca.laranja", "Técnico SCA Laranja"),
        ("sca.vermelho", "Técnico SCA Vermelho"),
    ]

    CONEXOES_SCA = ["wifi", "4g", "3g", "2g", "5g", "offline"]

    def _sca(self, tecnicos, upfs):
        agora = timezone.now()
        limiar = self._limiar_sync_dias()
        territorios = list(Territory.objects.order_by("pk"))
        role_tecnico = Role.objects.get(slug="adt-acr")

        sca_tecnicos = []
        for i, (usuario_local, nome) in enumerate(self.SCA_TECNICOS):
            email = f"{usuario_local}@{DEMO_EMAIL_DOMAIN}"
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email, nome=nome, password=DEMO_PASSWORD,
                )
            UserProfile.objects.get_or_create(
                user=user,
                perfil=role_tecnico,
                territorio=territorios[i % len(territorios)],
            )
            sca_tecnicos.append((user, territorios[i % len(territorios)]))

        faixas = [
            ("dev-seed-verde", agora - timedelta(minutes=30), [0, 1]),
            ("dev-seed-laranja", agora - timedelta(days=3), [2, 4]),
            ("dev-seed-vermelho", agora - timedelta(days=limiar + 2), [limiar + 2, limiar + 5]),
        ]

        conexoes = (self.CONEXOES_SCA * 3)[: len(faixas) * 3]
        dispositivos = {}
        eventos_criados = []
        for idx, (device_id, ultimo_sync, dias) in enumerate(faixas):
            tecnico, _ = sca_tecnicos[idx]
            device = SyncDevice.objects.create(
                user=tecnico,
                device_id=device_id,
                nome=device_id.replace("-", " ").title(),
                modelo=self.rnd.choice(["Samsung Galaxy A14", "Motorola Moto E13", "Xiaomi Redmi 9"]),
                sistema_operacional=self.rnd.choice(["Android 13", "Android 12", "Android 11"]),
                app_versao="1.4.0",
                ultimo_push_em=ultimo_sync,
                ultimo_pull_em=ultimo_sync - timedelta(minutes=self.rnd.randint(1, 10)),
            )
            dispositivos[device_id] = device
            plano_eventos = [
                ("push", dias[0], {"enviados": 9}),
                ("pull", dias[-1], {"recebidos": 38}),
            ]
            if device_id == "dev-seed-laranja":
                plano_eventos.append(("push", 3, {
                    "enviados": 6,
                    "erros": [
                        {"uuid_local": str(uuid4()), "entidade": "upf",
                         "codigo": "PAYLOAD_INVALIDO",
                         "mensagem": "CPF inválido no payload."},
                        {"uuid_local": str(uuid4()), "entidade": "activity",
                         "codigo": "FORA_TERRITORIO", "mensagem": ""},
                    ],
                }))
            else:
                plano_eventos.append(("pull", dias[0], {"recebidos": 17}))
            for tipo, dias_atras, kwargs in plano_eventos:
                evento = self._evento_sync(
                    tecnico, device, tipo, dias_atras,
                    conexoes.pop(0), agora=agora, **kwargs,
                )
                eventos_criados.append(evento.pk)
        SyncEvent.objects.filter(pk__in=eventos_criados).update(
            finalizado_em=F("iniciado_em") + timedelta(minutes=2),
        )

        territorio_a = sca_tecnicos[0][1]
        territorio_b = self._territorio_de_estado_distinto(territorio_a, territorios)
        tecnico_verde, tecnico_vermelho = sca_tecnicos[0][0], sca_tecnicos[-1][0]

        ConflictLog.objects.create(
            user=tecnico_verde,
            device=dispositivos["dev-seed-verde"],
            entidade="upf",
            uuid_local=uuid4(),
            campo="cpf",
            valor_local="333.555.888-00",
            valor_servidor="529.982.247-25",
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS,
            campo_sensivel=True,
            status=ConflictLog.Status.PENDENTE,
            territorio=territorio_a,
        )
        ConflictLog.objects.create(
            user=tecnico_vermelho,
            device=dispositivos["dev-seed-vermelho"],
            entidade="upf",
            uuid_local=uuid4(),
            campo="whatsapp",
            valor_local="(84) 99999-1111",
            valor_servidor="(84) 98888-2222",
            valor_final="(84) 98888-2222",
            estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS,
            campo_sensivel=False,
            status=ConflictLog.Status.RESOLVIDO_AUTO,
            resolvido_em=agora - timedelta(days=limiar + 1),
            territorio=territorio_b,
        )

        if upfs:
            UPF.objects.filter(pk=upfs[0].pk).update(
                device_id="dev-mock-001",
                uuid_local=uuid4(),
                ultima_origem="sca",
                ultimo_sync_em=agora - timedelta(hours=2),
            )
            MembroFamilia.objects.filter(pk=upfs[0].titular_id).update(
                device_id="dev-mock-001",
                uuid_local=uuid4(),
                ultima_origem="sca",
                ultimo_sync_em=agora - timedelta(hours=2),
            )
        atividade_base = Activity.objects.order_by("pk").first()
        if atividade_base:
            Activity.objects.filter(pk=atividade_base.pk).update(
                device_id="dev-mock-001",
                uuid_local=uuid4(),
                ultima_origem="sca",
                ultimo_sync_em=agora - timedelta(hours=2),
            )

        alvo_revogacao = next(
            (t for t in tecnicos if t.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")), None
        )
        if alvo_revogacao:
            User.objects.filter(pk=alvo_revogacao.pk).update(
                acesso_revogado=True,
                acesso_revogado_em=agora - timedelta(days=10),
            )

        self.stdout.write(
            "SCA: 3 técnicos com dispositivos nas faixas verde/laranja/vermelha, "
            f"{len(eventos_criados)} eventos de sync e 2 conflitos "
            "(1 pendente sensível, 1 resolvido automático)"
        )

    def _limiar_sync_dias(self) -> int:
        config, _ = SystemConfig.objects.get_or_create(
            chave="sca_sync_alerta_dias",
            defaults={
                "valor": "7",
                "tipo": "integer",
                "descricao": "Dias sem sincronização antes de alertar dispositivo SCA.",
            },
        )
        try:
            return int(config.valor)
        except (TypeError, ValueError):
            return 7

    def _evento_sync(self, usuario, device, tipo, dias_atras, conexao, *, agora,
                     enviados=0, recebidos=0, erros=None):
        erros = erros or []
        inicio = agora - timedelta(days=dias_atras, minutes=self.rnd.randint(3, 720))
        return SyncEvent.objects.create(
            user=usuario,
            device=device,
            tipo=tipo,
            contagem=max(enviados + recebidos, 1),
            contagem_enviados=enviados,
            contagem_recebidos=recebidos,
            contagem_erros=len(erros),
            erros_detalhes=list(erros),
            tipo_conexao=conexao,
            iniciado_em=inicio,
        )

    @staticmethod
    def _territorio_de_estado_distinto(referencia, territorios):
        estados_ref = set(referencia.estados or [])
        for territorio in territorios:
            if territorio.pk != referencia.pk and not (
                set(territorio.estados or []) & estados_ref
            ):
                return territorio
        return territorios[-1]

    def _resumo(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed de demonstração concluído."))
        for modelo in (
            Municipality, Organization, Comunidade, UPF, MembroFamilia, Production,
            UPFDocument, WorkPlanMeta, WorkPlanAcao, Activity, ActivityPhoto,
            ActivityDocument,
        ):
            self.stdout.write(
                f"  {modelo._meta.verbose_name_plural}: {modelo.objects.count()}"
            )
