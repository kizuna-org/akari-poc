"""Measures VAD to STT latency."""

from __future__ import annotations

import dataclasses
import threading
import time
import io

from typing import Optional

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)

# TC002: Move third-party import `akari_core.logger.AkariLogger` into a type-checking block
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from akari_core.logger import AkariLogger


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
        self._vad_start_time: float | None = None
        self._vad_end_time: float | None = None
        self._is_vad_end: bool = True

    def call(
        self,
        data: AkariData,
        params: _VADSTTLatencyMeterConfig,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Process data for VAD/STT latency measurement.

        This method processes data chunks in a streaming fashion,
        measuring latency between Voice Activity Detection (VAD)
        speech detection and the arrival of corresponding
        Speech-to-Text (STT) results.
        """
        # This module is designed for streaming, so call is not supported
        # ERA001: Found commented-out code (This is a comment, not commented out code)
        # not_implemented_msg = "VADSTTLatencyMeter does not support call method. Use stream_call instead."
        # raise NotImplementedError(not_implemented_msg)
        raise NotImplementedError(
            "VADSTTLatencyMeter does not support call method. Use stream_call instead."
        )

    def stream_call(
        self,
        data: AkariData,
        params: _VADSTTLatencyMeterConfig,
        callback: AkariModuleType | None = None,
    ) -> AkariData:
        """Analyze an incoming audio chunk for voice activity using WebRTC VAD.

        If speech is detected or ends, trigger the specified callback.
        """
        self._logger.debug("VADSTTLatencyMeter stream_call called")

        audio = data.last().audio
        if audio is None:
            # TRY003: Avoid specifying long messages outside the exception class
            # EM101: Exception must not use a string literal, assign to variable first
            error_msg = "Audio data is missing or empty."
            raise ValueError(error_msg)

        frame_size_bytes = int(
            params.frame_duration_ms
            * audio.sample_rate
            / 1000
            * audio.num_channels
            * audio.sample_width
        )
        if len(audio.main) < frame_size_bytes:
            # TRY003: Avoid specifying long messages outside the exception class
            # EM102: Exception must not use an f-string literal, assign to variable first
            error_msg = f"Audio data is too short. Expected at least {frame_size_bytes} bytes, but got {len(audio.main)} bytes."
            raise ValueError(error_msg)

        buffer = io.BytesIO(self._audio_buffer + audio.main)
        self._audio_buffer = buffer.getvalue()
        buffer.seek(-frame_size_bytes, io.SEEK_END)
        frame = buffer.read(frame_size_bytes)
        self._audio_buffer = buffer.getvalue()

        try:
            is_speech = self._vad.is_speech(frame, audio.sample_rate)
            self._logger.debug("WebRTC VAD detected speech: %s", is_speech)
        except Exception as e:  # BLE001: Do not catch blind exception: `Exception`
            # TRY003: Avoid specifying long messages outside the exception class
            # EM102: Exception must not use an f-string literal, assign to variable first
            error_msg = f"Error processing audio data with WebRTC VAD: {e}"
            raise ValueError(error_msg) from e

        dataset = AkariDataSet()
        dataset.bool = AkariDataSetType(main=is_speech)
        dataset.float = AkariDataSetType(main=time.time())

        # SIM102: Use a single `if` statement instead of nested `if` statements
        if callback and (
            (not params.callback_when_speech_ended and is_speech)
            or (
                params.callback_when_speech_ended
                and not is_speech
                and not self._callbacked
            )
        ):
            # FBT003: Boolean positional value in function call (Assuming True is intentional positional arg)
            data = self._router.callModule(
                callback, data, params.callback_params, True, None
            )
            self._callbacked = True
            self._audio_buffer = b""

        if not is_speech and self._callbacked:
            self._callbacked = False
            self._audio_buffer = b""

        data.append(dataset)
        return data
