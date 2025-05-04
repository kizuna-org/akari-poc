import dataclasses
import io
from typing import Any

import pyaudio

from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SpeakerModuleParams:
    format: int = pyaudio.paInt16
    rate: int | None = None
    channels: int | None = None
    chunk: int = 1024
    output_device_index: int | None = None


class _SpeakerModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def _play(self, buffer: io.BytesIO, params: _SpeakerModuleParams, channels: int, rate: int) -> None:
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
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        meta = data.last().meta

        channels = params.channels or meta.main.get("channels", 1) if meta else None
        rate = params.rate or meta.main.get("rate", 16000) if meta else None

        if channels is None or rate is None:
            raise ValueError("Channels and rate must be provided or available in metadata.")

        buffer = io.BytesIO(audio.stream.last() if audio.stream else audio.main)
        return buffer, channels, rate

    def call(
        self, data: AkariData, params: _SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        dataset = AkariDataSet()
        return dataset

    def stream_call(
        self, data: AkariData, params: _SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        dataset = AkariDataSet()
        return dataset
