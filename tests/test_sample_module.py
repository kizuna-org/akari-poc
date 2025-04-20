import pytest

from akari import AkariData, AkariDataSet, MainRouter
from sample.module import SampleModule


@pytest.fixture
def main_router() -> MainRouter:
    return MainRouter()


@pytest.fixture
def sample_module(main_router: MainRouter) -> SampleModule:
    return SampleModule(main_router)


def test_sample_module_call(sample_module: SampleModule) -> None:
    data = AkariData(last=AkariDataSet())

    result = sample_module.call(data, None)

    assert result == data
