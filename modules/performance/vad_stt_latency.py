import asyncio
import threading
import time
from typing import (
    AsyncGenerator,
    Optional,
    List,
    Any,
    Dict,
    cast,
)

from akari import (
    AkariModule,
    AkariModuleType,
    AkariRouter,
    AkariLogger,
    AkariData,
    AkariDataSet,
    AkariModuleParams,
    AkariDataModuleType,
)

_vad_start_time: Optional[float] = None


class _VADSTTLatencyMeterConfig:
    stt_module: AkariModuleType
    stt_module_params: AkariModuleParams
    vad_module: AkariModuleType
    vad_module_params: AkariModuleParams


class _VADSTTLatencyMeter(AkariModule):
    """Measures and logs the latency from voice activity detection (VAD) start to the completion of speech-to-text (STT) processing for the input audio stream.

    It splits the input audio stream and feeds it in parallel to a VAD module
    and an STT module. The STT module's output (TextData) is passed through.
    Latency is logged when the STT module finishes processing its input stream.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger):
        super().__init__(router, logger)

    def call(
        self, data: AkariData, params: _VADSTTLatencyMeterConfig, callback: AkariModuleType | None = None
    ) -> AkariData:
        raise NotImplementedError("This module does not support non-streaming operations.")

    def stream_call(
        self, data: AkariData, params: _VADSTTLatencyMeterConfig, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        global _vad_start_time

        def vad_func(data: AkariData) -> None:
            vad_data = self._router.callModule(params.vad_module, data, params.vad_module_params, True, None)
            if vad_data.datasets and vad_data.last().bool:
                global _vad_start_time
                _vad_start_time = time.time()

        if _vad_start_time is None:
            thread1 = threading.Thread(target=vad_func, args=(data,))
            thread1.start()

        stt_data = self._router.callModule(params.stt_module, data, params.stt_module_params, True, None)

        dataset = stt_data.last()
        dataset.setModule(
            AkariDataModuleType(
                _VADSTTLatencyMeter,
                params,
                True,
                callback,
                _vad_start_time if _vad_start_time is not None else -1,
                time.time(),
            )
        )

        if dataset.text:
            _vad_start_time = None

        return dataset
