"""Validação dos parâmetros globais (`SystemConfig`) na escrita, pela API e pelo Django Admin."""
import json

from rest_framework import serializers

from apps.core.models.system_config import SystemConfig, TipoConfiguracao

PERIODICIDADES_DO_LIMITE = ("mensal", "trimestral", "semestral", "vigencia")
LIMIARES_DO_SEMAFORO = {"budget_alert_yellow_pct": 70, "budget_alert_red_pct": 90}
FAIXA_DOS_PARAMETROS_DO_ORCAMENTO = {
    "budget_subexec_alert_months": (1, 24),
    "budget_subexec_min_pct": (1, 100),
    "budget_transfer_alert_pct": (1, 100),
    "budget_return_risk_alert_months": (1, 24),
    "budget_return_risk_pct": (1, 100),
    "budget_alert_yellow_pct": (1, 100),
    "budget_alert_red_pct": (1, 100),
}


def parametro_do_orcamento_invalido(chave: str, valor: str) -> str | None:
    """A mensagem do erro, se houver. `valor` já vem normalizado pelo tipo do parâmetro."""
    if chave == "budget_limit_period" and valor not in PERIODICIDADES_DO_LIMITE:
        return f"Use uma destas periodicidades: {', '.join(PERIODICIDADES_DO_LIMITE)}."
    if chave in FAIXA_DOS_PARAMETROS_DO_ORCAMENTO:
        minimo, maximo = FAIXA_DOS_PARAMETROS_DO_ORCAMENTO[chave]
        if not minimo <= int(valor) <= maximo:
            return f"Informe um valor de {minimo} a {maximo}."
    if chave in LIMIARES_DO_SEMAFORO:
        # Os dois limiares travados, sempre na mesma ordem: duas alterações simultâneas, uma em cada, não
        # passam juntas deixando o amarelo acima do vermelho. Quem chama está numa transação.
        gravados = dict(
            SystemConfig.objects.select_for_update().filter(chave__in=LIMIARES_DO_SEMAFORO)
            .order_by("chave").values_list("chave", "valor")
        )
        amarelo, vermelho = (
            int(valor) if chave == limiar else int(gravados.get(limiar, padrao))
            for limiar, padrao in LIMIARES_DO_SEMAFORO.items()
        )
        if amarelo >= vermelho:
            return f"O limiar amarelo ({amarelo}%) precisa ser menor que o vermelho ({vermelho}%)."
    return None


def valor_do_tipo(tipo: str, value) -> str:
    """O valor gravado em `SystemConfig.valor`, normalizado pelo tipo do parâmetro."""
    if tipo == TipoConfiguracao.INTEGER:
        try:
            return str(int(value))
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                f"Valor inválido para tipo INTEGER: '{value}' não é um número inteiro válido."
            )

    if tipo == TipoConfiguracao.BOOLEAN:
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            normalized = value.lower().strip()
            if normalized in ("true", "false", "1", "0"):
                return str(normalized in ("true", "1"))
        raise serializers.ValidationError(
            f"Valor inválido para tipo BOOLEAN: '{value}' não é um valor booleano válido."
        )

    if tipo == TipoConfiguracao.JSON:
        if isinstance(value, str):
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    f"Valor inválido para tipo JSON: '{value}' não é um JSON válido."
                )
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                "Valor inválido para tipo JSON: não foi possível serializar."
            )

    return str(value)
