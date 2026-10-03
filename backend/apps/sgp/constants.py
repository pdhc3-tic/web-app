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
    ("nenhuma", "Nenhuma"),
    ("diabetes", "Diabetes"),
    ("hipertensao", "Hipertensão"),
    ("deficiencia_visual", "Deficiência visual"),
    ("deficiencia_auditiva", "Deficiência auditiva"),
    ("deficiencia_motora", "Deficiência motora"),
    ("deficiencia_intelectual", "Deficiência intelectual"),
    ("deficiencia_multipla", "Deficiência múltipla"),
    ("doenca_cardiaca", "Doença cardíaca"),
    ("doenca_respiratoria", "Doença respiratória"),
    ("doenca_renal", "Doença renal"),
    ("saude_mental", "Saúde mental"),
    ("gestante", "Gestante"),
    ("lactante", "Lactante"),
    ("desnutricao", "Desnutrição"),
    ("alergia_alimentar", "Alergia alimentar"),
    ("doenca_cronica", "Doença crônica"),
    ("outros", "Outros"),
]

SEGURIDADE_SOCIAL_CHOICES = [
    ("bpc", "BPC/LOAS"),
    ("bolsa_familia", "Bolsa Família"),
    ("aposentadoria", "Aposentadoria"),
    ("nenhum", "Nenhum"),
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

STATUS_NO_PRAZO = "no_prazo"
STATUS_EM_ATRASO = "em_atraso"
STATUS_CONCLUIDA = "concluida"

STATUS_WORKPLAN = [
    (STATUS_NO_PRAZO, "No Prazo"),
    (STATUS_EM_ATRASO, "Em Atraso"),
    (STATUS_CONCLUIDA, "Concluída"),
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
