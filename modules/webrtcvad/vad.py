import dataclasses
import io
from enum import Enum
from typing import Any

import pyaudio
import webrtcvad

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
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
    sample_rate: int = 16000
    frame_duration_ms: int = 30


class _WebRTCVadModule(AkariModule):
    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        super().__init__(router, logger)
        self.vad = webrtcvad.Vad()

    def call(self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        raise NotImplementedError("WebRTCVadModule does not support call method. Use stream_call instead.")

    def stream_call(
        self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        buffer = io.BytesIO(audio.main)
        frame_size = int(params.sample_rate * params.frame_duration_ms / 1000)
        if len(audio.main) < frame_size:
            raise ValueError(
                f"Audio data is too short. Expected at least {frame_size} bytes, but got {len(audio.main)} bytes."
            )

        buffer.seek(-frame_size, io.SEEK_END)
        audio_data = buffer.read(frame_size)

        try:
            is_speech = self.vad.is_speech(audio_data, params.sample_rate)
        except Exception as e:
            raise ValueError(f"Error processing audio data: {e}")

        dataset = AkariDataSet()
        dataset.bool = AkariDataSetType(is_speech)

        return dataset
