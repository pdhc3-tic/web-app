from datetime import date, timedelta

import holidays

DIAS_UTEIS_LIMITE = 5


def feriados(uf: str | None, inicio: date, fim: date) -> holidays.HolidayBase:
    """Feriados nacionais + estaduais da UF. Feriado municipal fica de fora —
    a lib não cobre municípios."""
    subdiv = uf if uf in holidays.BR.subdivisions else None
    return holidays.country_holidays("BR", subdiv=subdiv, years=range(inicio.year, fim.year + 1))


def dias_uteis_entre(
    inicio: date, fim: date, *, uf: str | None = None, feriados_do_periodo: holidays.HolidayBase | None = None,
) -> int:
    """Dias úteis (segunda–sexta, fora feriados) entre `inicio` (exclusive) e
    `fim` (inclusive). `feriados_do_periodo` permite reaproveitar o calendário
    de uma UF em vários cálculos (evita recriar o `HolidayBase` por demanda)."""
    calendario = feriados_do_periodo if feriados_do_periodo is not None else feriados(uf, inicio, fim)
    dias = 0
    atual = inicio
    while atual < fim:
        atual += timedelta(days=1)
        if atual.weekday() < 5 and atual not in calendario:
            dias += 1
    return dias
