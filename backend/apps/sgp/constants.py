GENERO_CHOICES = [
    (1, "Masculino"),
    (2, "Feminino"),
    (3, "Não binário"),
    (4, "Não informado"),
]

COR_RACA_CHOICES = [
    (1, "Branca"),
    (2, "Preta"),
    (3, "Parda"),
    (4, "Amarela"),
    (5, "Indígena"),
]

ESCOLARIDADE_CHOICES = [
    (1, "Sem instrução"),
    (2, "Fundamental incompleto"),
    (3, "Fundamental completo"),
    (4, "Médio incompleto"),
    (5, "Médio completo"),
    (6, "Superior incompleto"),
    (7, "Superior completo"),
]

DISPOSITIVO_CHOICES = [
    (1, "Computador"),
    (2, "Notebook"),
    (3, "Tablet"),
    (4, "Smartphone"),
    (5, "Não possui"),
    (6, "Outro"),
]

PCT_CHOICES = [
    (1, "Sim"),
    (2, "Não"),
    (3, "Não Informado"),
]

POSSE_TERRA_CHOICES = [
    (1, "Própria"),
    (2, "Alugada"),
    (3, "Cedida"),
    (4, "Ocupação"),
    (5, "Posse tradicional"),
    (6, "Não Informado"),
]

SITUACAO_MORADIA_CHOICES = [
    (1, "Própria"),
    (2, "Alugada"),
    (3, "Cedida"),
    (4, "Ocupação"),
    (5, "Financiada"),
    (6, "Não Informado"),
]

TIPO_MORADIA_CHOICES = [
    (1, "Casa"),
    (2, "Apartamento"),
    (3, "Cômodo"),
    (4, "Barraca"),
    (5, "Outro"),
    (6, "Não Informado"),
]

MATERIAL_CONSTRUCAO_CHOICES = [
    (1, "Alvenaria"),
    (2, "Madeira"),
    (3, "Taipa"),
    (4, "Pedra"),
    (5, "Misto"),
    (6, "Outro"),
    (7, "Não Informado"),
]

ENERGIA_CHOICES = [
    (1, "Sim"),
    (2, "Não"),
    (3, "Não Informado"),
]

AGUA_CHOICES = [
    (1, "Rede pública"),
    (2, "Poço artesiano"),
    (3, "Poço raso"),
    (4, "Nascente"),
    (5, "Carro-pipa"),
    (6, "Chuva"),
    (7, "Outro"),
    (8, "Não Informado"),
]

SAUDE_CHOICES = [
    "nenhuma",
    "diabetes",
    "hipertensao",
    "deficiencia_visual",
    "deficiencia_auditiva",
    "deficiencia_motora",
    "deficiencia_intelectual",
    "deficiencia_multipla",
    "doenca_cardiaca",
    "doenca_respiratoria",
    "doenca_renal",
    "saude_mental",
    "gestante",
    "lactante",
    "desnutricao",
    "alergia_alimentar",
    "doenca_cronica",
    "outros",
]

SEGURIDADE_SOCIAL_CHOICES = [
    "bpc",
    "bolsa_familia",
    "aposentadoria",
    "nenhum",
]

PARENTESCO_CHOICES = [
    ("titular", "Titular"),
    ("conjuge", "Cônjuge"),
    ("filho", "Filho(a)"),
    ("enteado", "Enteado(a)"),
    ("pai", "Pai"),
    ("mae", "Mãe"),
    ("irmao", "Irmão(ã)"),
    ("avo", "Avô(ó)"),
    ("neto", "Neto(a)"),
    ("outro", "Outro"),
]

# ---------------------------------------------------------------------------
# Plano de Trabalho — Metas & Ações
# ---------------------------------------------------------------------------

STATUS_WORKPLAN = [
    ("no_prazo", "No Prazo"),
    ("em_atraso", "Em Atraso"),
    ("concluida", "Concluída"),
]

TIPO_UNIDADE_MEDIDA = [
    (1, "Seminário"),
    (2, "Oficina"),
    (3, "Curso / Capacitação"),
    (4, "Plano"),
    (5, "Relatório de pesquisas"),
    (6, "Intercâmbio"),
    (7, "Conteúdo audiovisual"),
    (8, "Visita técnica"),
    (9, "Encontro / Reunião"),
    (10, "Unidade implementada"),
    (11, "Família atendida"),
    (12, "Outro"),
]

ODS_CHOICES = [
    (1, "ODS 1 – Erradicação da Pobreza"),
    (2, "ODS 2 – Fome Zero e Agricultura Sustentável"),
    (3, "ODS 3 – Saúde e Bem-Estar"),
    (4, "ODS 4 – Educação de Qualidade"),
    (5, "ODS 5 – Igualdade de Gênero"),
    (6, "ODS 6 – Água Potável e Saneamento"),
    (7, "ODS 7 – Energia Acessível e Limpa"),
    (8, "ODS 8 – Trabalho Decente e Crescimento Econômico"),
    (9, "ODS 9 – Indústria, Inovação e Infraestrutura"),
    (10, "ODS 10 – Redução das Desigualdades"),
    (11, "ODS 11 – Cidades e Comunidades Sustentáveis"),
    (12, "ODS 12 – Consumo e Produção Responsáveis"),
    (13, "ODS 13 – Ação contra a Mudança Global do Clima"),
    (14, "ODS 14 – Vida na Água"),
    (15, "ODS 15 – Vida Terrestre"),
    (16, "ODS 16 – Paz, Justiça e Instituições Eficazes"),
    (17, "ODS 17 – Parcerias e Meios de Implementação"),
]
