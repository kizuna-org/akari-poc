import asyncio
import dataclasses
import threading
import time
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    cast,
)

from akari import (
    AkariData,
    AkariDataModuleType,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
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
    """Measures and logs the latency from voice activity detection (VAD) start to the completion of speech-to-text (STT) processing for the input audio stream.

    It splits the input audio stream and feeds it in parallel to a VAD module
    and an STT module. The STT module's output (TextData) is passed through.
    Latency is logged when the STT module finishes processing its input stream.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger):
        super().__init__(router, logger)
        self._vad_start_time: Optional[float] = None
        self._vad_end_time: Optional[float] = None
        self._is_vad_end: bool = True

    def call(
        self, data: AkariData, params: _VADSTTLatencyMeterConfig, callback: AkariModuleType | None = None
    ) -> AkariData:
        raise NotImplementedError("This module does not support non-streaming operations.")

    def stream_call(
        self, data: AkariData, params: _VADSTTLatencyMeterConfig, callback: AkariModuleType | None = None
    ) -> AkariDataSet:

        def vad_func(data: AkariData) -> None:
            vad_data = self._router.callModule(params.vad_module, data, params.vad_module_params, True, None)
            bool_data = vad_data.last().bool
            flag = bool_data.main if bool_data else None
            if flag and self._vad_start_time is None and self._is_vad_end:
                self._vad_start_time = time.perf_counter()
                self._is_vad_end = False
            if not flag:
                if not self._is_vad_end:
                    self._vad_end_time = time.perf_counter()
                self._is_vad_end = True
                self._vad_start_time = None

        thread1 = None
        if self._vad_start_time is None:
            thread1 = threading.Thread(target=vad_func, args=(data,))
            thread1.start()

        stt_data = self._router.callModule(params.stt_module, data, params.stt_module_params, True, None)

        dataset = stt_data.last()
        now = time.perf_counter()
        dataset.setModule(
            AkariDataModuleType(
                _VADSTTLatencyMeter,
                params,
                True,
                callback,
                (
                    self._vad_end_time
                    if self._vad_end_time is not None
                    else self._vad_start_time if self._vad_start_time is not None else now
                ),
                now,
            )
        )

        if dataset.text and dataset.text.main == "":
            self._vad_start_time = None
            self._vad_end_time = None

        if thread1:
            thread1.join()

        def callback_func(data: AkariData) -> None:
            if callback:
                self._router.callModule(callback, data, params.callback_params, True, None)

        data.add(dataset)
        thread2 = threading.Thread(target=callback_func, args=(data,))
        thread2.start()

        return dataset
