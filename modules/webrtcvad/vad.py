import dataclasses
import io
import time
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
    speech_sleep_duration_ms: int = 0
    callback_when_speech_ended: bool = False
    callback_params: AkariModuleParams | None = None


class _WebRTCVadModule(AkariModule):
    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        super().__init__(router, logger)
        self._vad = webrtcvad.Vad()
        self._last_speech_time = time.mktime(time.gmtime(0))
        self._callbacked = True
        self._audio_buffer: bytes = b""

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
            self._logger.debug("WebRTC VAD detected speech: %s", is_speech)
        except Exception as e:
            raise ValueError(f"Error processing audio data with WebRTC VAD: {e}") from e

        dataset = AkariDataSet()
        dataset.bool = AkariDataSetType(is_speech)
        dataset.audio = AkariDataSetType(main=self._audio_buffer, others={"all": audio_data})
        dataset.meta = data.last().meta
        data.add(dataset)

        if is_speech:
            self._last_speech_time = time.time()
            self._callbacked = False
            if audio.stream is not None:
                self._audio_buffer += audio.stream.last()
        else:
            if time.time() - self._last_speech_time < params.speech_sleep_duration_ms / 1000:
                is_speech = True

        self._logger.debug("WebRTC VAD functional detected speech: %s", is_speech)

        if callback:
            if (not params.callback_when_speech_ended and is_speech) or (
                params.callback_when_speech_ended and not is_speech and not self._callbacked
            ):
                data = self._router.callModule(callback, data, params.callback_params, True, None)
                self._callbacked = True
                self._audio_buffer = b""

        return data
