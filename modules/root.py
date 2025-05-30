"""Akari root module."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING  # TC002

if TYPE_CHECKING:
    from akari_core.logger import AkariLogger

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _RootModuleParams(AkariModuleParams):
    """RootModuleのパラメータ."""

    first_module_type: AkariModuleType
    """最初に呼び出すモジュール."""
    first_module_params: AkariModuleParams | None = None
    """最初に呼び出すモジュールに渡すパラメータ."""


class _RootModule(AkariModule):  # Class cannot subclass "AkariModule" (has type "Any") - skipping for now
    """Akariパイプラインのエントリポイントとなるモジュール."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """RootModuleを初期化します."""
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: _RootModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Initiate the Akari pipeline by invoking the first module."""
        self._logger.debug("RootModule call called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        # ERA001 removed
        # ERA001 removed
        # E501 - will rely on xc format

        # For now, just return the input data as is, assuming downstream modules will process it.
        return data.last() if data.datasets else AkariDataSet()

    def stream_call(
        self,
        data: AkariData,
        params: AkariModuleParams,  # ARG002 - keeping for now
        callback: AkariModuleType | None = None,  # ARG002 - keeping for now
    ) -> AkariDataSet:
        """Initiate the Akari streaming pipeline by invoking the first module."""
        self._logger.debug("RootModule stream_call called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        # This module is designed to pass data to the first module in a streaming fashion
        # For now, just return the input data as is, assuming downstream modules will process it.
        return data.last() if data.datasets else AkariDataSet()
