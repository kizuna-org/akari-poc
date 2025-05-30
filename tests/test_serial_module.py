from __future__ import annotations  # For good practice

import pytest
from faker import Faker

from akari import AkariData, AkariDataSet, AkariDataSetType, AkariLogger, AkariRouter
from modules import (
    PrintModule,
    SerialModule,
    SerialModuleParamModule,
    SerialModuleParams,
)


@pytest.fixture(scope="session")
def fakegen() -> Faker:
    return Faker()


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


def test_serial_module_call(fakegen: Faker, router: AkariRouter) -> None:
    data = AkariData()
    dataset = AkariDataSet()
    dataset.text = AkariDataSetType(fakegen.word())
    data.add(dataset)

    serial_module_params = SerialModuleParams(
        modules=[
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
            SerialModuleParamModule(moduleType=PrintModule, moduleParams={}, moduleCallback=None),
        ],
    )

    result = router.call_module(
        SerialModule,
        data,
        serial_module_params,
        False,
        None,
    )  # N802 (from router change)

    assert isinstance(result, AkariData)  # noqa: S101
    assert len(result.datasets) == 1 + 3  # noqa: S101
    assert result.datasets[0].text == dataset.text  # noqa: S101
    for i in range(1, 4):
        assert isinstance(result.datasets[i], AkariDataSet)  # noqa: S101
