import pytest

from akari import AkariData, AkariDataSet, AkariLogger, MainRouter
from sample.module import _SampleModule


@pytest.fixture
def main_router(logger: AkariLogger) -> MainRouter:
    return MainRouter(logger=logger)


@pytest.fixture
def logger() -> AkariLogger:
    return AkariLogger("test")


@pytest.fixture
def sample_module(main_router: MainRouter, logger: AkariLogger) -> _SampleModule:
    return _SampleModule(main_router, logger)


def test_sample_module_call(sample_module: _SampleModule) -> None:
    data = AkariData()

    result = sample_module.call(data, None)

    assert isinstance(result, AkariDataSet)
