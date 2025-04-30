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
    rate: int = 24000
    channels: int = 1
    chunk: int = 1024
    output_device_index: int | None = None


class _SpeakerModule(AkariModule):
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(
        self, data: AkariData, params: _SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        buffer = io.BytesIO(audio.main)
        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=params.format,
                channels=params.channels,
                rate=params.rate,
                output=True,
                frames_per_buffer=params.chunk,
                output_device_index=params.output_device_index,
            )

            sample_width = p.get_sample_size(params.format)
            bytes_per_buffer = sample_width * params.channels
            audio_data = buffer.read(params.chunk * bytes_per_buffer)
            while audio_data:
                stream.write(audio_data)
                audio_data = buffer.read(params.chunk * bytes_per_buffer)

            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()

        dataset = AkariDataSet()
        return dataset

    def stream_call(
        self, data: AkariData, params: _SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        if audio.stream is None:
            raise ValueError("Audio stream data is missing or empty.")
        buffer = io.BytesIO(audio.stream.last())
        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=params.format,
                channels=params.channels,
                rate=params.rate,
                output=True,
                frames_per_buffer=params.chunk,
            )

            audio_data = buffer.read(params.chunk)
            while audio_data:
                stream.write(audio_data)
                audio_data = buffer.read(params.chunk)

            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()

        dataset = AkariDataSet()
        return dataset
