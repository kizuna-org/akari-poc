import dataclasses
import io
import wave
from typing import Any

import pyaudio

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    MainRouter,
)


@dataclasses.dataclass
class SpeakerModuleParams:
    format: int = pyaudio.paInt16
    rate: int = 24000
    channels: int = 1
    chunk: int = 1024


class SpeakerModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(
        self, data: AkariData, params: SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        buffer = io.BytesIO(audio.main)
        with wave.open(buffer, "rb") as wf:
            p = pyaudio.PyAudio()
            try:
                stream = p.open(
                    format=params.format,
                    channels=params.channels,
                    rate=params.rate,
                    output=True,
                    frames_per_buffer=params.chunk,
                )

                audio_data = wf.readframes(params.chunk)
                while audio_data:
                    stream.write(audio_data)
                    audio_data = wf.readframes(params.chunk)

                stream.stop_stream()
                stream.close()
            finally:
                p.terminate()

        dataset = AkariDataSet()
        return dataset
