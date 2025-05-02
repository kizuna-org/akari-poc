import dataclasses
import io
from enum import Enum
from typing import Any, Literal

import pyaudio
import webrtcvad

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _WebRTCVadMode(Enum):
    VERY_SENSITIVE = 0
    SENSITIVE = 1
    LOW_SENSITIVE = 2
    STRICT = 3


@dataclasses.dataclass
class _WebRTCVadParams:
    mode: _WebRTCVadMode = _WebRTCVadMode.VERY_SENSITIVE
    sample_rate: Literal[8000, 16000, 32000, 48000] = 16000
    frame_duration_ms: Literal[10, 20, 30] = 30
    callback_params: AkariModuleParams | None = None


class _WebRTCVadModule(AkariModule):
    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        super().__init__(router, logger)
        self._vad = webrtcvad.Vad()

    def call(self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        raise NotImplementedError("WebRTCVadModule does not support call method. Use stream_call instead.")

    def stream_call(
        self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None
    ) -> AkariData:
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        self._vad.set_mode(params.mode.value)

        buffer = io.BytesIO(audio.main)
        frame_size_bytes = int(params.sample_rate * params.frame_duration_ms / 1000 * 2)

        if len(audio.main) < frame_size_bytes:
            raise ValueError(
                f"Audio data is too short. Expected at least {frame_size_bytes} bytes, but got {len(audio.main)} bytes."
            )

        buffer.seek(-frame_size_bytes, io.SEEK_END)
        audio_data = buffer.read(frame_size_bytes)

        try:
            is_speech = self._vad.is_speech(audio_data, params.sample_rate)
        except Exception as e:
            raise ValueError(f"Error processing audio data with WebRTC VAD: {e}")

        dataset = AkariDataSet()
        dataset.bool = AkariDataSetType(is_speech)
        data.add(dataset)

        if is_speech and callback:
            data = self._router.callModule(callback, data, params.callback_params, True, None)

        return data
