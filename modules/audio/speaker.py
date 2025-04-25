import dataclasses
import io
import wave
from typing import Any

import pyaudio
from pydub import AudioSegment

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
    format: str


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

        audio_segment = AudioSegment.from_file(buffer, format="mp3")
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)

        with wave.open(wav_io, "rb") as wf:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )

            audio_data = wf.readframes(1024)
            while audio_data:
                stream.write(audio_data)
                audio_data = wf.readframes(1024)

            stream.stop_stream()
            stream.close()
            p.terminate()

        dataset = AkariDataSet()
        return dataset
