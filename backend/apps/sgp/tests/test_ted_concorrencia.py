import threading
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.core.tests.factories import RoleFactory, StateFactory, UserFactory
from apps.sgp.models import TED, BudgetPool, TEDVersionRubrica
from apps.sgp.tests.factories import BudgetPoolFactory, BudgetRubricaFactory, TEDVersionFactory

Nivel = BudgetPool.Nivel
URL = "/api/v1/sgp/ted/"
POOLS_URL = "/api/v1/sgp/orcamento/pools/"
CHAVE = "ted/documentos/0b6f4c1e-3a5d-4f7e-9c2b-1d8e7f6a5b4c.pdf"
OUTRA_CHAVE = "ted/documentos/7c1e2d3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f.pdf"
REMANEJAR_URL = "/api/v1/sgp/orcamento/remanejamentos/"


class _StoragePDF:
    def head_object(self, key):
        return {"ContentType": "application/pdf", "ContentLength": 2048}


def _em_paralelo(*chamadas):
    """Roda cada chamada numa thread com conexão própria, soltas juntas por uma
    barreira, e devolve os status HTTP na ordem das chamadas."""
    barreira = threading.Barrier(len(chamadas))
    resultados = [None] * len(chamadas)
    erros = []

    def rodar(indice, chamada):
        try:
            barreira.wait()
            resultados[indice] = chamada().status_code
        except Exception as exc:
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=rodar, args=(i, c)) for i, c in enumerate(chamadas)]
    with mock.patch("apps.sgp.ted.services.get_storage", return_value=_StoragePDF()):
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    if erros:
        raise erros[0]
    return resultados


class TestOperacoesNoPoolNacionalContraAditivo(TransactionTestCase):
    """TransactionTestCase porque as gravações precisam de conexões reais
    concorrentes: o django_db do pytest roda o teste numa transação só.

    Diárias tem R$ 1.000 aprovados e o pool nacional em R$ 500. Material tem
    R$ 1.000 aprovados e ainda não tem pool. O aditivo baixa os dois para R$ 600."""

    def setUp(self):
        self.usuario = UserFactory(
            email="ted-concorrencia@test.com", profiles=[(RoleFactory(slug="super-admin", nome="Super Admin"), None)],
        )
        self.diarias = BudgetRubricaFactory()
        self.material = BudgetRubricaFactory()
        versao = TEDVersionFactory(valor_global=Decimal("2000"))
        for rubrica in (self.diarias, self.material):
            TEDVersionRubrica.objects.create(versao=versao, rubrica=rubrica, valor_aprovado=Decimal("1000"))
        self.ted = versao.ted
        self.nacional = BudgetPoolFactory(
            rubrica=self.diarias, nivel=Nivel.NACIONAL, estado=None, territorio=None,
            valor_alocado=Decimal("500"), ted_versao=versao,
        )

    def _cliente(self):
        cliente = APIClient()
        cliente.force_authenticate(user=self.usuario)
        return cliente

    def _aditivo(self, chave=CHAVE, valor="600.00"):
        def registrar():
            return self._cliente().post(
                f"{URL}{self.ted.pk}/versoes/",
                {
                    "tipo": "aditivo", "motivo": "Redução das rubricas", "vigencia_inicio": "2025-11-01",
                    "vigencia_fim": "2028-10-31", "valor_global": str(Decimal(valor) * 2),
                    "rubricas": [
                        {"rubrica": self.diarias.pk, "valor_aprovado": valor},
                        {"rubrica": self.material.pk, "valor_aprovado": valor},
                    ],
                    "documento_key": chave,
                },
                format="json",
            )

        return registrar

    def _assert_pools_dentro_do_aprovado_vigente(self):
        self.ted.refresh_from_db()
        aprovado = dict(
            TEDVersionRubrica.objects.filter(versao=self.ted.versao_vigente).values_list("rubrica_id", "valor_aprovado")
        )
        for pool in BudgetPool.objects.filter(nivel=Nivel.NACIONAL):
            assert pool.valor_alocado <= aprovado[pool.rubrica_id]
            assert pool.ted_versao_id == self.ted.versao_vigente_id

    def test_aumento_do_pool_nacional(self):
        def aumento():
            return self._cliente().patch(
                f"{POOLS_URL}{self.nacional.pk}/", {"valor_alocado": "1000.00"}, format="json",
            )

        resultados = _em_paralelo(aumento, self._aditivo())

        assert sorted(resultados) in ([200, 400], [201, 400])
        self._assert_pools_dentro_do_aprovado_vigente()

    def test_criacao_do_pool_nacional(self):
        def criacao():
            return self._cliente().post(
                POOLS_URL,
                {"rubrica_id": self.material.pk, "nivel": "nacional", "valor_alocado": "1000.00"},
                format="json",
            )

        resultados = _em_paralelo(criacao, self._aditivo())

        assert sorted(resultados) == [201, 400]
        self._assert_pools_dentro_do_aprovado_vigente()

    def test_remanejamento_do_estadual_para_o_nacional(self):
        estadual = BudgetPoolFactory(
            rubrica=self.diarias, nivel=Nivel.ESTADUAL, estado=StateFactory(sigla="RN", nome="Rio Grande do Norte"),
            territorio=None, valor_alocado=Decimal("300"), ted_versao=self.ted.versao_vigente,
        )

        def remanejamento():
            return self._cliente().post(
                REMANEJAR_URL,
                {
                    "origem_allocation": estadual.pk, "destino_allocation": self.nacional.pk,
                    "valor": "300.00", "justificativa": "Devolução ao nacional.",
                },
                format="json",
            )

        resultados = _em_paralelo(remanejamento, self._aditivo())

        assert sorted(resultados) == [201, 400]
        self._assert_pools_dentro_do_aprovado_vigente()

    def test_dois_aditivos_ganham_numeros_seguidos(self):
        resultados = _em_paralelo(self._aditivo(CHAVE), self._aditivo(OUTRA_CHAVE, valor="700.00"))

        assert resultados == [201, 201]
        self.ted.refresh_from_db()
        assert sorted(self.ted.versoes.values_list("numero_versao", flat=True)) == [1, 2, 3]
        assert self.ted.versao_vigente.numero_versao == 3
        self._assert_pools_dentro_do_aprovado_vigente()


class TestCadastroSimultaneoDoTED(TransactionTestCase):
    def setUp(self):
        self.usuario = UserFactory(
            email="ted-cadastro@test.com", profiles=[(RoleFactory(slug="ugp", nome="UGP"), None)],
        )
        self.rubrica = BudgetRubricaFactory()

    def _cadastro(self, numero):
        def cadastrar():
            cliente = APIClient()
            cliente.force_authenticate(user=self.usuario)
            return cliente.post(
                URL,
                {
                    "numero": numero, "participes": ["MDA", "UFERSA"],
                    "versao": {
                        "vigencia_inicio": "2025-11-01", "vigencia_fim": "2028-10-31", "valor_global": "100.00",
                        "rubricas": [{"rubrica": self.rubrica.pk, "valor_aprovado": "100.00"}],
                        "documento_key": CHAVE,
                    },
                },
                format="json",
            )

        return cadastrar

    def test_so_um_ted_e_cadastrado(self):
        resultados = _em_paralelo(self._cadastro("TED 01/2025"), self._cadastro("TED 02/2025"))

        assert sorted(resultados) == [201, 400]
        assert TED.objects.count() == 1
