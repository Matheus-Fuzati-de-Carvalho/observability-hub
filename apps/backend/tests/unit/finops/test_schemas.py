import pytest
from pydantic import TypeAdapter, ValidationError

from observability_hub.domains.finops.schemas import MinDaysUnused


# Regressão: query params do FastAPI sempre chegam como string
# ("?min_days_unused=30" -> "30"). Literal[30, 60, 90] não faz essa
# coerção (exige o tipo exato, sem lax-coercion) e causava 422 em toda
# chamada real — só se manifestava no request de verdade, invisível pros
# testes de service/repository (que chamam as funções direto com int
# nativo, nunca passam pela validação de query param). IntEnum resolve.
def test_min_days_unused_coerces_from_query_string():
    result = TypeAdapter(MinDaysUnused).validate_python("30")
    assert result == MinDaysUnused.THIRTY


@pytest.mark.parametrize("raw", ["30", "60", "90"])
def test_min_days_unused_accepts_all_allowed_values_as_string(raw):
    assert TypeAdapter(MinDaysUnused).validate_python(raw) == int(raw)


def test_min_days_unused_rejects_value_outside_allowed_set():
    with pytest.raises(ValidationError):
        TypeAdapter(MinDaysUnused).validate_python("45")
