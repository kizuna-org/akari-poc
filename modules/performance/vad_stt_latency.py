"""Measures VAD to STT latency."""

from __future__ import annotations

import dataclasses
import threading
import time
from typing import Optional

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
class _VADSTTLatencyMeterConfig:
    stt_module: AkariModuleType
    stt_module_params: AkariModuleParams
    vad_module: AkariModuleType
    vad_module_params: AkariModuleParams
    callback_params: AkariModuleParams


class _VADSTTLatencyMeter(AkariModule):
    """VAD (Voice Activity Detection)からSTT (Speech-to-Text) までのレイテンシを計測するモジュール.

    音声ストリームにおいて、VADが音声の開始を検出してから、対応する音声の文字起こしが完了するまでの時間を計測します.
    これは、会話AIなどにおいてユーザーの発話に対するシステムの応答速度を評価するのに役立ちます.
    モジュールはストリーミングモードでのみ動作し、VADモジュールとSTTモジュールを内部で呼び出します.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """VADSTTLatencyMeterを初期化します."""
        super().__init__(router, logger)
        self._vad_start_time: Optional[float] = None
        self._vad_end_time: Optional[float] = None
        self._is_vad_end: bool = True

    def call(
        self,
        data: AkariData,
        params: _VADSTTLatencyMeterConfig,
        _callback: AkariModuleType | None = None,  # ARG002: Unused method argument
    ) -> AkariData:
        """Standard, non-streaming invocation (not supported for this module)."""
        # EM101: Exception must not use a string literal, assign to variable first
        not_implemented_msg = "This module does not support non-streaming operations."
        raise NotImplementedError(not_implemented_msg)

    def stream_call(
        self,
        data: AkariData,
        params: _VADSTTLatencyMeterConfig,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Analyzes stream data for VAD and forwards to STT, measuring latency."""

        def vad_func(data: AkariData) -> None:
            # FBT003: Use keyword argument for streaming
            vad_data = self._router.callModule(
                params.vad_module,
                data,
                params.vad_module_params,
                streaming=True,
                callback=None,
            )
            bool_data = vad_data.last().bool
            flag = bool_data.main if bool_data else None

            # Check VAD status and update timestamps
            current_time = time.perf_counter()
            if flag is True and self._is_vad_end:
                self._vad_start_time = current_time
                self._is_vad_end = False
                self._logger.debug("VAD start detected at %f", self._vad_start_time)
            elif flag is False and not self._is_vad_end:
                self._vad_end_time = current_time
                self._is_vad_end = True
                self._logger.debug("VAD end detected at %f", self._vad_end_time)

        # Run VAD check in a separate thread to avoid blocking STT processing
        thread1 = threading.Thread(target=vad_func, args=(data,))
        thread1.start()

        # Forward the same data to the STT module
        # FBT003: Use keyword argument for streaming
        stt_data = self._router.callModule(
            params.stt_module,
            data,
            params.stt_module_params,
            streaming=True,
            callback=None,
        )

        dataset = stt_data.last()

        # If STT result is final and VAD start time is recorded, calculate and log latency
        if (
            dataset.meta
            and dataset.meta.main
            and "is_final" in dataset.meta.main
            and dataset.meta.main["is_final"]
            and self._vad_start_time is not None
        ):
            stt_end_time = time.perf_counter()
            latency = stt_end_time - self._vad_start_time
            self._logger.info(
                "STT Final Result Received. Latency (VAD Start to STT Final): %f seconds",
                latency,
            )

            # Reset VAD start time after calculating latency for a final result
            self._vad_start_time = None

        # Handle downstream callback if provided and STT result is final or callback_when_final is False
        # FBT003: Use keyword argument for streaming
        if callback:
            if (
                dataset.meta
                and dataset.meta.main
                and "is_final" in dataset.meta.main
                and dataset.meta.main["is_final"]
            ) or not (
                hasattr(params, "callback_when_final")
                and params.callback_when_final is False
            ):
                self._router.callModule(
                    callback,
                    data,
                    params.callback_params,
                    streaming=True,
                    callback=None,
                )

        data.add(dataset)
        return data
