from __future__ import annotations  # For good practice, though not strictly needed for this file's changes yet

from typing import Any  # For mock type hints

import pytest
from akari_core.logger import AkariLogger as CoreAkariLogger  # Alias to avoid F821 if AkariLogger is defined locally
from akari_core.router import AkariRouter as CoreAkariRouter  # Alias to avoid F821 if AkariRouter is defined locally

from akari import AkariData, AkariDataSet
from sample.module import _SampleModule


@pytest.fixture
def main_router(logger: CoreAkariLogger) -> CoreAkariRouter:  # Use aliased type
    return CoreAkariRouter(logger=logger)


@pytest.fixture
def logger() -> CoreAkariLogger:  # Use aliased type
    return CoreAkariLogger("test")


@pytest.fixture
def sample_module(main_router: CoreAkariRouter, logger: CoreAkariLogger) -> _SampleModule:  # Use aliased types
    return _SampleModule(main_router, logger)


def test_sample_module_call() -> None:  # ANN201
    # Create mock AkariRouter and AkariLogger
    # F821 - AkariRouter and AkariLogger might need specific mock objects if they are complex
    # For now, using simple mocks or assuming they can be instantiated directly if no complex dependencies
    try:
        # These are from akari_core, which might not be available during linting in this context
        router = CoreAkariRouter(logger=CoreAkariLogger("mock"))  # Use aliased type
        logger_instance = CoreAkariLogger("mock")  # Use aliased type, renamed to avoid conflict
    except NameError:  # Catch NameError if akari_core types aren't found
        # Provide simple mock objects if instantiation fails
        class MockRouter:
            def call_module(self, *args: Any, **kwargs: Any) -> None:  # N802, ANN002, ANN003, ANN202 # noqa: ANN401
                pass

        class MockLogger:
            def debug(self, *args: Any, **kwargs: Any) -> None:  # ANN002, ANN003, ANN202 # noqa: ANN401
                pass

            def info(self, *args: Any, **kwargs: Any) -> None:  # ANN002, ANN003, ANN202 # noqa: ANN401
                pass

            def warning(self, *args: Any, **kwargs: Any) -> None:  # ANN002, ANN003, ANN202 # noqa: ANN401
                pass

            def error(self, *args: Any, **kwargs: Any) -> None:  # ANN002, ANN003, ANN202 # noqa: ANN401
                pass

            def exception(self, *args: Any, **kwargs: Any) -> None:  # ANN002, ANN003, ANN202 # noqa: ANN401
                pass

        router = MockRouter()
        logger_instance = MockLogger()  # Use the mock instance

    sample_module = _SampleModule(router, logger_instance)  # Use potentially mocked logger_instance
    data = AkariData()

    result = sample_module.call(data, None)

    assert isinstance(result, AkariDataSet)  # noqa: S101
