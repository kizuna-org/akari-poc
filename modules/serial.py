"""Akari serial module."""

from __future__ import annotations

import dataclasses
import time
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
class _SerialModuleParams(AkariModuleParams):
    """SerialModule用のパラメータ."""

    message_interval_ms: int = 100
    """メッセージ間の遅延時間(ミリ秒). デフォルトは100ms."""


class _SerialModule(AkariModule):
    """AkariDataの各DataSetを逐次(シリアルに)処理するモジュール."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """SerialModuleを初期化します."""
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: _SerialModuleParams,
        callback: AkariModuleType | None = None,  # ARG002 - keeping for now
    ) -> AkariDataSet:
        """Process each DataSet in AkariData sequentially with a delay."""
        self._logger.debug("SerialModule call called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        result_data = AkariData()

        for dataset in data.datasets:
            result_data.add(dataset)
            if callback:
                self._router.callModule(callback, result_data, None, streaming=True)

            time.sleep(params.message_interval_ms / 1000)

        # After processing all datasets, call the callback one last time with the full result
        if callback:
            self._router.callModule(callback, result_data, None, streaming=False)

        # Return the accumulated data, though in a serial processing context,
        # the primary interaction is via callbacks.
        return result_data.last() if result_data.datasets else AkariDataSet()

    # stream_call is not typically used for a serial processing module like this
    # If streaming input is received, it will be processed by the call method anyway.
