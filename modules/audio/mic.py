from __future__ import annotations

import dataclasses
import threading
import time
from typing import Any

import pyaudio

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _MicModuleParams:
    """Defines configuration settings for microphone audio capture.

    Controls aspects like audio format (sample rate, channels, PyAudio format),
    device selection, chunking behavior for processing, and how callback
    modules are invoked with the captured audio data.

    Attributes:
        format (int): The PyAudio format constant for samples (e.g., `pyaudio.paInt16`).
            Determines sample size and type. Defaults to `pyaudio.paInt16`.
        rate (int): The desired sampling rate in Hertz (samples per second).
            Common values include 16000, 24000, 44100, 48000. Defaults to 24000.
        channels (int): The number of audio channels to record (e.g., 1 for mono,
            2 for stereo). Defaults to 1.
        frames_per_buffer (int): The number of audio frames PyAudio should read
            in a single operation. This influences latency and processing granularity.
            Defaults to 1024.
        input_device_index (Optional[int]): The numerical index of the audio input
            device to use. If `None`, PyAudio's default input device is selected.
            Defaults to None.
        streamDurationMilliseconds (int): Specifies the duration, in milliseconds,
            of each audio segment that is collected before being dispatched to
            the callback module. Defaults to 500 ms.
        destructionMilliseconds (int): Defines a sliding window, in milliseconds.
            Audio frames older than this duration (relative to the newest frame
            in the current processing segment) are discarded from the internal
            buffer. This helps manage memory for continuous recording. Defaults to 500 ms.
        callback_when_thread_is_alive (bool): Governs whether a new callback
            can be initiated if the previous callback thread is still running.
            If False (default), a new callback is only started if the previous one
            has completed. If True, new callbacks can be launched concurrently.
            Defaults to False.
        callbackParams (Any | None): Arbitrary parameters that will be passed to
            the callback module when it's invoked. This allows contextual
            information to be sent alongside the audio data. Defaults to None.
        callback_callback (Optional[AkariModuleType]): The class type of the Akari
            module to be called when an audio segment (of `streamDurationMilliseconds`)
            is ready. This module will receive the recorded audio data.
            Defaults to None, meaning no callback will be triggered.
    """

    format: int = pyaudio.paInt16
    rate: int = 24000
    channels: int = 1
    frames_per_buffer: int = 1024
    input_device_index: int | None = None
    stream_duration_milliseconds: int = 5 * 100  # N815
    destruction_milliseconds: int = 5 * 100  # N815
    callback_when_thread_is_alive: bool = False
    callback_params: Any | None = None  # N815
    callback_callback: AkariModuleType | None = None


class _MicModule(AkariModule):
    """Captures audio input from a designated microphone device.

    Manages a continuous recording loop, processing incoming audio into
    configurable chunks. For each complete chunk, it can dispatch the audio
    data (along with associated metadata) to a specified callback Akari module
    for further processing (e.g., speech-to-text, VAD). Callbacks are executed
    in separate threads to avoid blocking the main recording loop.

    Attributes:
        _thread (threading.Thread): Stores the currently active callback thread,
            if any. This helps manage concurrent callback executions based on
            module parameters.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a MicModule instance.

        Initializes the base AkariModule and prepares a placeholder for managing
        the callback thread.

        Args:
            router (AkariRouter): The Akari router instance, used to invoke
                callback modules.
            logger (AkariLogger): The logger instance for recording operational
                details and debugging information.
        """
        super().__init__(router, logger)
        self._thread: threading.Thread = threading.Thread()

    def call(self, _data: AkariData, params: _MicModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet: # ARG002: data -> _data
        """Initiates and manages the continuous audio recording loop from the microphone.

        Opens a PyAudio stream configured by `params`. It then enters an infinite
        loop, reading audio data in chunks. These chunks are accumulated until
        `params.streamDurationMilliseconds` of audio is collected. At this point,
        an `AkariDataSet` is created containing the accumulated audio (as `main`
        and in a stream) and relevant metadata (channels, sample width, rate).

        If a `callback` module (specified by `params.callback_callback`) is configured,
        a new thread is spawned to invoke this callback module via the AkariRouter,
        passing the newly created `AkariData` (containing the audio dataset) and
        `params.callbackParams`. The behavior of launching new threads when one
        is already active is controlled by `params.callback_when_thread_is_alive`.

        The method maintains a sliding window of audio frames based on
        `params.destructionMilliseconds` to manage memory.

        Note:
            This method runs an infinite loop and is expected to be terminated
            by an external event (e.g., `KeyboardInterrupt` in a typical script,
            or by the application managing the Akari pipeline). The `data` argument
            is used as a template for creating new `AkariData` instances for
            callbacks, but the input `data` itself is not directly modified or used
            as input audio. The primary output is via the callback mechanism.

        Args:
            data (AkariData): An initial (usually empty) AkariData object.
            params (_MicModuleParams): Configuration parameters for the microphone
                recording, chunking, and callback behavior.
            callback (Optional[AkariModuleType]): The Akari module type specified
                in `params.callback_callback` is the one actually used for the
                threaded callback. This top-level `callback` argument is effectively
                ignored in the current implementation logic for the threaded callback.

        Returns:
            AkariDataSet: An empty `AkariDataSet`. The actual audio data is
            dispatched through the threaded callback mechanism.

        Raises:
            PyAudioException: If there are issues opening or reading from the
                audio stream (e.g., device not found, invalid parameters).
            Exception: Other exceptions might occur depending on PyAudio and
                system audio configuration.
        """
        dataset = AkariDataSet()

        audio = pyaudio.PyAudio()

        streamer = audio.open(
            format=params.format,
            channels=params.channels,
            rate=params.rate,
            input=True,
            frames_per_buffer=params.frames_per_buffer,
            input_device_index=params.input_device_index,
        )

        self._logger.info("Recording started...")
        try:
            frames = []
            frame = b""
            frame_time = time.time()
            streamer.start_stream()

            while True:
                data_chunk = streamer.read(params.frames_per_buffer, exception_on_overflow=False)
                frame += data_chunk

                current_time = time.time()
                if current_time - frame_time >= params.stream_duration_milliseconds / 1000:  # N815
                    frames.append(frame)

                    current_call_data = AkariData() # Renamed data to avoid B023 in lambda
                    dataset = AkariDataSet()
                    stream = AkariDataStreamType(frames)
                    dataset.audio = AkariDataSetType(main=b"".join(frames), stream=stream)
                    dataset.meta = AkariDataSetType(
                        main={
                            "channels": params.channels,
                            "sample_width": audio.get_sample_size(params.format),
                            "rate": params.rate,
                        },
                    )
                    current_call_data.add(dataset)
                    if callback is not None:

                        def call_module_in_thread() -> None:
                            self._router.call_module( # N802 (from akari.router change)
                                module_type=callback, # N803 (from akari.router change)
                                data=current_call_data,  # noqa: B023 - data is intentionally from outer scope but new for each call
                                params=params.callback_params, # N815
                                streaming=True,
                                callback=params.callback_callback,
                            )

                        if not self._thread.is_alive() or params.callback_when_thread_is_alive:
                            self._thread = threading.Thread(target=call_module_in_thread)
                            self._thread.start()

                    frame_time = current_time
                    frame = b""

                if len(frames) >= params.destruction_milliseconds / params.stream_duration_milliseconds: # N815
                    frames = frames[1:]

        finally:
            streamer.stop_stream()
            streamer.close()
            audio.terminate()
