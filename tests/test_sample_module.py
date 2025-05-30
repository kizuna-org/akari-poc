import pytest
from akari_core.logger import AkariLogger
from akari_core.router import AkariRouter

from akari import AkariData, AkariDataSet
from sample.module import _SampleModule


@pytest.fixture
def main_router(logger: AkariLogger) -> AkariRouter:
    return AkariRouter(logger=logger)


@pytest.fixture
def logger() -> AkariLogger:
    return AkariLogger("test")


@pytest.fixture
def sample_module(main_router: AkariRouter, logger: AkariLogger) -> _SampleModule:
    return _SampleModule(main_router, logger)


def test_sample_module_call():
    # Create mock AkariRouter and AkariLogger
    # F821 - AkariRouter and AkariLogger might need specific mock objects if they are complex
    # For now, using simple mocks or assuming they can be instantiated directly if no complex dependencies
    try:
        router = AkariRouter()
        logger = AkariLogger()
    except TypeError:  # Handle potential issues with direct instantiation
        # Provide simple mock objects if instantiation fails
        class MockRouter:
            def callModule(self, *args, **kwargs):  # FBT003 fixed by keeping the argument
                pass

        class MockLogger:
            def debug(self, *args, **kwargs):
                pass

            def info(self, *args, **kwargs):
                pass

            def warning(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

            def exception(self, *args, **kwargs):
                pass

        router = MockRouter()
        logger = MockLogger()

    sample_module = _SampleModule(router, logger)
    data = AkariData()

    result = sample_module.call(data, None)

    assert isinstance(result, AkariDataSet)  # S101 - keeping for now
