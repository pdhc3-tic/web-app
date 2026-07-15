from django.db import migrations


CULTURAS = [
    ("Milho", "Zea mays", "graos", "anual"),
    ("Feijão Carioca", "Phaseolus vulgaris", "graos", "anual"),
    ("Feijão Preto", "Phaseolus vulgaris", "graos", "anual"),
    ("Feijão Caupi", "Vigna unguiculata", "leguminosas", "anual"),
    ("Feijão Verde", "Vigna unguiculata", "leguminosas", "anual"),
    ("Arroz", "Oryza sativa", "graos", "anual"),
    ("Sorgo", "Sorghum bicolor", "graos", "anual"),
    ("Mandioca", "Manihot esculenta", "raizes", "perene"),
    ("Macaxeira", "Manihot esculenta", "raizes", "perene"),
    ("Batata-doce", "Ipomoea batatas", "raizes", "anual"),
    ("Inhame", "Dioscorea spp.", "raizes", "anual"),
    ("Banana", "Musa spp.", "frutas", "perene"),
    ("Manga", "Mangifera indica", "frutas", "perene"),
    ("Mamão", "Carica papaya", "frutas", "perene"),
    ("Melancia", "Citrullus lanatus", "frutas", "anual"),
    ("Melão", "Cucumis melo", "frutas", "anual"),
    ("Maracujá", "Passiflora edulis", "frutas", "perene"),
    ("Goiaba", "Psidium guajava", "frutas", "perene"),
    ("Caju", "Anacardium occidentale", "frutas", "perene"),
    ("Acerola", "Malpighia emarginata", "frutas", "perene"),
    ("Coco", "Cocos nucifera", "frutas", "perene"),
    ("Graviola", "Annona muricata", "frutas", "perene"),
    ("Pinha", "Annona squamosa", "frutas", "perene"),
    ("Limão", "Citrus limon", "frutas", "perene"),
    ("Laranja", "Citrus sinensis", "frutas", "perene"),
    ("Abacaxi", "Ananas comosus", "frutas", "perene"),
    ("Tomate", "Solanum lycopersicum", "hortalicas", "anual"),
    ("Pimentão", "Capsicum annuum", "hortalicas", "anual"),
    ("Coentro", "Coriandrum sativum", "hortalicas", "anual"),
    ("Alface", "Lactuca sativa", "hortalicas", "anual"),
    ("Cebola", "Allium cepa", "hortalicas", "anual"),
    ("Cebolinha", "Allium schoenoprasum", "hortalicas", "anual"),
    ("Quiabo", "Abelmoschus esculentus", "hortalicas", "anual"),
    ("Jerimum", "Cucurbita spp.", "hortalicas", "anual"),
    ("Maxixe", "Cucumis anguria", "hortalicas", "anual"),
    ("Gergelim", "Sesamum indicum", "oleaginosas", "anual"),
    ("Mamona", "Ricinus communis", "oleaginosas", "anual"),
    ("Amendoim", "Arachis hypogaea", "oleaginosas", "anual"),
    ("Girassol", "Helianthus annuus", "oleaginosas", "anual"),
    ("Algodão", "Gossypium hirsutum", "fibrosas", "anual"),
    ("Sisal", "Agave sisalana", "fibrosas", "perene"),
    ("Palma Forrageira", "Opuntia ficus-indica", "forrageiras", "perene"),
    ("Capim Buffel", "Cenchrus ciliaris", "forrageiras", "perene"),
    ("Capim Elefante", "Pennisetum purpureum", "forrageiras", "perene"),
    ("Gliricídia", "Gliricidia sepium", "forrageiras", "perene"),
    ("Leucena", "Leucaena leucocephala", "forrageiras", "perene"),
    ("Cana-de-açúcar", "Saccharum officinarum", "outras", "perene"),
    ("Urucum", "Bixa orellana", "outras", "perene"),
    ("Hibisco", "Hibiscus sabdariffa", "medicinais", "anual"),
    ("Erva-cidreira", "Melissa officinalis", "medicinais", "perene"),
    ("Hortelã", "Mentha spp.", "medicinais", "perene"),
    ("Babosa", "Aloe vera", "medicinais", "perene"),
    ("Rosa do Deserto", "Adenium obesum", "ornamentais", "perene"),
]


ESPECIES_ANIMAIS = [
    ("Bovino de corte", "bovino"),
    ("Bovino leiteiro", "bovino"),
    ("Bovino misto", "bovino"),
    ("Caprino de corte", "caprino"),
    ("Caprino leiteiro", "caprino"),
    ("Ovino de corte", "ovino"),
    ("Ovino leiteiro", "ovino"),
    ("Suíno", "suino"),
    ("Galinha caipira", "aves"),
    ("Galinha poedeira", "aves"),
    ("Frango de corte", "aves"),
    ("Pato", "aves"),
    ("Peru", "aves"),
    ("Codorna", "aves"),
    ("Equino", "equino"),
    ("Muar", "equino"),
    ("Tilápia", "piscicultura"),
    ("Tambaqui", "piscicultura"),
    ("Peixe nativo", "piscicultura"),
    ("Abelha Apis", "apicultura"),
    ("Abelha Jataí", "apicultura"),
    ("Abelha Uruçu", "apicultura"),
]


def seed_catalogos(apps, schema_editor):
    Cultura = apps.get_model("sgp", "Cultura")
    EspecieAnimal = apps.get_model("sgp", "EspecieAnimal")

    for nome, nome_cientifico, categoria, ciclo in CULTURAS:
        Cultura.objects.get_or_create(
            nome=nome,
            defaults={
                "nome_cientifico": nome_cientifico,
                "categoria": categoria,
                "ciclo": ciclo,
                "ativa": True,
            },
        )

    for nome, categoria in ESPECIES_ANIMAIS:
        EspecieAnimal.objects.get_or_create(
            nome=nome,
            defaults={"categoria": categoria, "ativa": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0004_catalogos"),
    ]

    operations = [
        migrations.RunPython(seed_catalogos, migrations.RunPython.noop),
    ]
