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
    """Specifies the sensitivity level for the WebRTC Voice Activity Detector (VAD).

    The VAD aggressiveness determines how likely it is to classify an audio
    frame as speech. A higher numeric mode corresponds to a more aggressive
    (less sensitive) VAD that is more restrictive in identifying speech.

    Attributes:
        VERY_SENSITIVE (int): Mode 0. Least aggressive, most likely to classify
            audio as speech. Suitable for environments with low background noise.
        SENSITIVE (int): Mode 1. A balanced level of sensitivity.
        LOW_SENSITIVE (int): Mode 2. More aggressive than SENSITIVE, less likely
            to classify borderline audio as speech.
        STRICT (int): Mode 3. Most aggressive, most restrictive in classifying
            audio as speech. Best for noisy environments where clear speech
            detection is paramount.
    """

    VERY_SENSITIVE = 0
    SENSITIVE = 1
    LOW_SENSITIVE = 2
    STRICT = 3


@dataclasses.dataclass
class _WebRTCVadParams:
    """Configures the behavior of the WebRTC VAD module.

    Settings include VAD sensitivity, expected audio properties (sample rate, frame
    duration), and logic for triggering callbacks based on speech events.

    Attributes:
        mode (_WebRTCVadMode): Determines the aggressiveness of the VAD algorithm.
            Higher modes are more restrictive in classifying audio as speech.
            Defaults to `_WebRTCVadMode.VERY_SENSITIVE`.
        sample_rate (Literal[8000, 16000, 32000, 48000]): The sample rate of the
            input audio, in Hertz. The WebRTC VAD library supports specific rates.
            Defaults to 16000 Hz.
        frame_duration_ms (Literal[10, 20, 30]): The duration of individual audio
            frames, in milliseconds, that the VAD processes. The WebRTC VAD
            library supports specific frame durations. Defaults to 30 ms.
        speech_sleep_duration_ms (int): A hysteresis mechanism. If the VAD detects
            non-speech, but speech was detected within this many milliseconds prior,
            the module can functionally treat it as continued speech. This helps
            avoid prematurely cutting off speech segments. A value of 0 disables
            this feature. Defaults to 0.
        callback_when_speech_ended (bool): Controls callback timing. If `True`,
            the configured callback module is invoked only when a speech segment
            ends (i.e., a transition from speech to non-speech, considering
            `speech_sleep_duration_ms`). If `False`, the callback is invoked
            upon any frame classified as speech (or functionally speech).
            Defaults to `False`.
        callback_params (Optional[AkariModuleParams]): Arbitrary parameters to be
            passed to the callback module when it's invoked by this VAD module.
            This allows contextual data to flow through the pipeline. Defaults to `None`.
    """

    mode: _WebRTCVadMode = _WebRTCVadMode.VERY_SENSITIVE
    sample_rate: Literal[8000, 16000, 32000, 48000] = 16000
    frame_duration_ms: Literal[10, 20, 30] = 30
    speech_sleep_duration_ms: int = 0
    callback_when_speech_ended: bool = False
    callback_params: AkariModuleParams | None = None


class _WebRTCVadModule(AkariModule):
    """Detects speech segments in real-time audio streams using the WebRTC Voice Activity Detection engine.

    This module is designed for streaming audio data. It analyzes incoming audio
    chunks frame by frame, determines if each frame contains speech, and manages
    an internal buffer of audio segments identified as speech. Based on configured
    parameters, it can trigger a callback Akari module when speech starts or ends,
    passing along the accumulated speech audio.

    Attributes:
        _vad (webrtcvad.Vad): An instance of the WebRTC VAD algorithm.
        _last_speech_time (float): Timestamp of the last frame detected as speech.
            Used for implementing `speech_sleep_duration_ms`.
        _callbacked (bool): Flag indicating if a callback has been made for the
            current speech segment, to avoid redundant callbacks.
        _audio_buffer (bytes): Accumulates audio frames that are part of the
            current speech segment. This buffer is sent to the callback module.
    """

    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        """Constructs a _WebRTCVadModule instance.

        Initializes the WebRTC VAD object and internal state variables for
        tracking speech timing, callback status, and audio buffering.

        Args:
            router (AkariRouter): The Akari router instance, used for invoking
                the configured callback module.
            logger (AkariLogger): The logger instance for recording VAD activity,
                speech detection events, and errors.
        """
        super().__init__(router, logger)
        self._vad = webrtcvad.Vad()
        self._last_speech_time = time.mktime(time.gmtime(0))
        self._callbacked = True
        self._audio_buffer: bytes = b""

    def call(self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Standard, non-streaming invocation (not supported for this module).

        The WebRTC VAD module is inherently stream-oriented as it processes audio
        chunks over time to detect speech segments. Therefore, it does not
        implement a traditional blocking `call` method.

        Args:
            data (AkariData): Input data (unused).
            params (_WebRTCVadParams): VAD parameters (unused).
            callback (Optional[AkariModuleType]): Callback module (unused).

        Raises:
            NotImplementedError: Always raised, as this module requires `stream_call`.
        """
        raise NotImplementedError("WebRTCVadModule does not support call method. Use stream_call instead.")

    def stream_call(
        self, data: AkariData, params: _WebRTCVadParams, callback: AkariModuleType | None = None
    ) -> AkariData:
        """Analyzes an incoming audio chunk for voice activity using the WebRTC VAD algorithm.

        This method expects an audio chunk in `data.last().audio.main`. It processes
        this chunk according to the configured `params` (mode, sample rate, frame duration).
        If speech is detected, the audio chunk (from `data.last().audio.stream.last()`
        if available, otherwise `data.last().audio.main`) is appended to an internal
        `_audio_buffer`.

        A callback mechanism is implemented based on `params.callback_when_speech_ended`
        and `params.speech_sleep_duration_ms`.
        - If `callback_when_speech_ended` is False, the callback is triggered as soon
          as speech (or functional speech considering `speech_sleep_duration_ms`) is detected.
        - If `callback_when_speech_ended` is True, the callback is triggered only when a
          speech segment ends (i.e., VAD reports non-speech after a period of speech,
          and the `speech_sleep_duration_ms` hysteresis has passed).

        When a callback is triggered, the accumulated `_audio_buffer` is sent to the
        specified `callback` module via the AkariRouter. The buffer is then cleared.
        The method updates the input `AkariData` object with a new `AkariDataSet`
        containing the boolean VAD result for the current chunk and the state of the
        audio buffer.

        Args:
            data (AkariData): The `AkariData` object containing the latest audio chunk.
                Expected audio location: `data.last().audio.main` for the VAD frame,
                and `data.last().audio.stream.last()` (or `.main`) for buffering.
            params (_WebRTCVadParams): Configuration parameters for VAD sensitivity,
                audio properties, and callback logic.
            callback (Optional[AkariModuleType]): The Akari module type to be invoked
                when a speech event (start or end, per configuration) occurs.

        Returns:
            AkariData: The modified `AkariData` object, which includes a new
            `AkariDataSet` with the VAD's boolean output for the processed frame
            and details of the current audio buffer.

        Raises:
            ValueError: If `data.last().audio` is missing or empty, if the audio
                chunk is too short for the configured frame size, or if an error
                occurs during `self._vad.is_speech()`.
        """
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
