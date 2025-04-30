from typing import List

import pytest

from akari import AkariData, AkariDataSet, AkariLogger, AkariRouter
from modules import (
    PrintModule,
    SerialModule,
    SerialModuleParamModule,
    SerialModuleParams,
)


@pytest.fixture(scope="session")
def router(logger: AkariLogger) -> AkariRouter:
    return AkariRouter(logger=logger)


@pytest.fixture(scope="session")
def logger() -> AkariLogger:
    return AkariLogger("test")


@pytest.fixture(scope="session", autouse=True)
def serial_module(router: AkariRouter, logger: AkariLogger) -> SerialModule:
    module = SerialModule(router, logger)
    router.addModules({SerialModule: module})
    return module


@pytest.fixture(scope="session", autouse=True)
def print_module(router: AkariRouter, logger: AkariLogger) -> PrintModule:
    module = PrintModule(router, logger)
    router.addModules({PrintModule: module})
    return module


def test_serial_module_call(router: AkariRouter) -> None:
    data = AkariData()
    data.add(AkariDataSet())

    serial_module_params = SerialModuleParams(
        modules=[
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
        ]
    )

    result = router.callModule(SerialModule, data, serial_module_params, False, None)

    assert isinstance(result, AkariData)
    assert len(result.datasets) == 1 + 3
