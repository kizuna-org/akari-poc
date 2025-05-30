from __future__ import annotations

import dataclasses
import io

import pyaudio

from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariRouter,
)


@dataclasses.dataclass
class _SpeakerModuleParams:
    """Defines settings for audio playback via a speaker.

    Includes configurations for audio format (sample type, rate, channels),
    the specific output device to use, and buffering parameters for playback.

    Attributes:
        format (int): The PyAudio format constant for audio samples (e.g.,
            `pyaudio.paInt16` for 16-bit signed integers). This determines the
            bit depth and type of each audio sample. Defaults to `pyaudio.paInt16`.
        rate (Optional[int]): The desired sampling rate in Hertz (samples per
            second) for playback. If set to `None`, the module will attempt to
            derive the rate from the input audio's metadata. Defaults to `None`.
        channels (Optional[int]): The number of audio channels (e.g., 1 for mono,
            2 for stereo). If `None`, the module attempts to get this from the
            input audio's metadata. Defaults to `None`.
        chunk (int): The number of audio frames to read from the input buffer and
            write to the output stream at a time. This can affect playback latency
            and smoothness. Defaults to 1024 frames.
        output_device_index (Optional[int]): The numerical index of the audio output
            device to use for playback. If `None`, PyAudio's default output
            device is selected. Defaults to `None`.
    """

    format: int = pyaudio.paInt16
    rate: int | None = None
    channels: int | None = None
    chunk: int = 1024
    output_device_index: int | None = None


class _SpeakerModule(AkariModule):
    """Facilitates audio playback through a system's speaker or selected audio output device.

    Retrieves audio data from an `AkariDataSet`, potentially using associated
    metadata for playback parameters (like sample rate and channels), and then
    streams this data to the chosen audio output using the PyAudio library.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a SpeakerModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for base module
                initialization (though not directly for playback logic).
            logger (AkariLogger): The logger instance for recording operational
                details, such as playback errors or informational messages.
        """
        super().__init__(router, logger)

    def _play(self, buffer: io.BytesIO, params: _SpeakerModuleParams, channels: int, rate: int) -> None:
        """Handles the low-level audio playback using PyAudio.

        Opens a PyAudio output stream configured with the provided parameters.
        It then reads audio data in chunks from the `buffer` and writes these
        chunks to the stream until the buffer is exhausted. Ensures that PyAudio
        resources are properly released after playback.

        Args:
            buffer (io.BytesIO): A byte stream containing the raw audio data to be played.
            params (_SpeakerModuleParams): Playback configuration, including format,
                chunk size, and output device index.
            channels (int): The number of channels in the audio data.
            rate (int): The sampling rate (in Hz) of the audio data.
        """
        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=params.format,
                channels=channels,
                rate=rate,
                output=True,
                frames_per_buffer=params.chunk,
                **(
                    {"output_device_index": params.output_device_index}
                    if params.output_device_index is not None
                    else {}
                ),
            )

            sample_width = p.get_sample_size(params.format)
            bytes_per_buffer = sample_width * channels
            audio_data = buffer.read(params.chunk * bytes_per_buffer)
            while audio_data:
                stream.write(audio_data)
                audio_data = buffer.read(params.chunk * bytes_per_buffer)

            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()

    def _prepare_audio(self, data: AkariData, params: _SpeakerModuleParams) -> tuple[io.BytesIO, int, int]:
        """Extracts and validates audio data and essential playback parameters from an AkariData object.

        This method attempts to retrieve the audio content (as bytes) from the
        last `AkariDataSet` in the provided `AkariData`. It also determines the
        number of channels and the sampling rate, prioritizing values explicitly
        set in `params` and falling back to metadata stored within the `AkariDataSet`
        if available.

        Args:
            data (AkariData): The `AkariData` instance from which to extract audio.
                The audio is expected in `data.last().audio`, and metadata in
                `data.last().meta`.
            params (_SpeakerModuleParams): Configuration parameters that may override
                or provide missing audio properties like channels and rate.

        Returns:
            tuple[io.BytesIO, int, int]: A tuple where the first element is an
            `io.BytesIO` buffer containing the audio data, the second is the
            number of channels, and the third is the sampling rate.

        Raises:
            ValueError: If the audio data field (`data.last().audio`) is missing
                or empty, or if the number of channels or sampling rate cannot be
                determined either from `params` or the audio metadata.
        """
        audio = data.last().audio
        if audio is None:
            # EM101, TRY003
            msg = "Audio data is missing or empty."
            raise ValueError(msg)

        meta = data.last().meta

        channels = params.channels or meta.main.get("channels", 1) if meta else None
        rate = params.rate or meta.main.get("rate", 16000) if meta else None

        if channels is None or rate is None:
            # EM101, TRY003
            msg = "Channels and rate must be provided or available in metadata."
            raise ValueError(msg)

        buffer = io.BytesIO(audio.stream.last() if audio.stream and audio.stream._delta else audio.main) # Access _delta for check
        return buffer, channels, rate

    def call(  # ARG002: callback removed
        self,
        data: AkariData,
        params: _SpeakerModuleParams,
    ) -> AkariDataSet:
        """Orchestrates the playback of audio data contained within the latest dataset of an AkariData sequence.

        This method first calls `_prepare_audio` to extract the audio bytes and
        determine necessary playback parameters (channels, rate). It then invokes
        the `_play` method to perform the actual audio output.

        Args:
            data (AkariData): The `AkariData` object containing the audio data,
                typically in the `audio` field of its last `AkariDataSet`.
            params (_SpeakerModuleParams): Configuration parameters for playback,
                such as output device, audio format, etc.
            callback (Optional[AkariModuleType]): An optional callback module.
                This parameter is currently not used by the SpeakerModule.

        Returns:
            AkariDataSet: An empty `AkariDataSet`, as the module's primary effect
            is audio output, not data transformation or generation.
        """
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        return AkariDataSet()  # RET504 fixed

    def stream_call(  # ARG002: callback removed
        self,
        data: AkariData,
        params: _SpeakerModuleParams,
    ) -> AkariDataSet:
        """Processes audio data for playback identically to the non-streaming `call` method.

        This module does not implement distinct logic for streaming versus
        non-streaming calls. Both invoke the same audio preparation and playback
        sequence.

        Args:
            data (AkariData): The `AkariData` object containing the audio.
            params (_SpeakerModuleParams): Playback configuration parameters.
            callback (Optional[AkariModuleType]): An optional callback module,
                currently unused.

        Returns:
            AkariDataSet: An empty `AkariDataSet`.
        """
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        return AkariDataSet()  # RET504 fixed
