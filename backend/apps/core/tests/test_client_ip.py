import pytest
from django.test import RequestFactory, override_settings

from apps.core.utils import get_client_ip


def _ip(forwarded=None, remote="10.0.0.2"):
    extra = {"REMOTE_ADDR": remote}
    if forwarded is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded
    return get_client_ip(RequestFactory().get("/", **extra))


def test_sem_proxy_usa_o_remote_addr():
    assert _ip() == "10.0.0.2"


def test_atras_do_nginx_usa_o_ip_que_ele_acrescentou_e_ignora_o_forjado():
    assert _ip("6.6.6.6, 203.0.113.9") == "203.0.113.9"


def test_cliente_sem_forjar_nada_tem_o_proprio_ip_na_cadeia():
    assert _ip("203.0.113.9") == "203.0.113.9"


@override_settings(TRUSTED_PROXY_COUNT=2)
def test_com_dois_proxies_confiaveis_pega_o_segundo_da_direita():
    assert _ip("6.6.6.6, 203.0.113.9, 192.0.2.50") == "203.0.113.9"


@override_settings(TRUSTED_PROXY_COUNT=2)
def test_cadeia_mais_curta_que_os_proxies_esperados_cai_no_remote_addr():
    assert _ip("203.0.113.9") == "10.0.0.2"


@override_settings(TRUSTED_PROXY_COUNT=0)
def test_sem_proxy_confiavel_ignora_o_cabecalho():
    assert _ip("6.6.6.6") == "10.0.0.2"


@pytest.mark.parametrize("forwarded", ["lixo", "999.1.1.1", "' OR 1=1 --"])
def test_valor_que_nao_e_ip_cai_no_remote_addr(forwarded):
    assert _ip(forwarded) == "10.0.0.2"


def test_ipv6():
    assert _ip("2001:db8::1") == "2001:db8::1"


def test_sem_nenhum_ip_devolve_none():
    assert get_client_ip(RequestFactory().get("/", REMOTE_ADDR="")) is None
