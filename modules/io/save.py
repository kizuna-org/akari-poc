import dataclasses
import time
import wave
from datetime import datetime

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


@dataclasses.dataclass
class _SaveModuleParams:
    file_path: str
    save_from_data: str
    with_timestamp: bool = False


class _SaveModule(AkariModule):
    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SaveModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        try:
            data.last().__dict__[params.save_from_data]
        except KeyError:
            raise ValueError(f"Data does not contain the key '{params.save_from_data}'.")
        if not data.last().__dict__[params.save_from_data]:
            raise ValueError(f"Data does not contain the key '{params.save_from_data}' or it is empty.")

        path = params.file_path
        if params.with_timestamp:
            paths = path.split(".")
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            if len(paths) > 1:
                path = f"{'.'.join(paths[:-1])}_{timestamp}.{paths[-1]}"
            else:
                path = f"{path}_{timestamp}"

        if path.endswith(".wav") and params.save_from_data == "audio":
            audio_data = data.last().__dict__[params.save_from_data]
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(audio_data.channels if hasattr(audio_data, "channels") else 1)
                wav_file.setsampwidth(audio_data.sample_width if hasattr(audio_data, "sample_width") else 2)
                wav_file.setframerate(audio_data.rate if hasattr(audio_data, "rate") else 16000)
                wav_file.writeframes(audio_data.main)
            self._logger.debug("Audio data saved as WAV to %s", path)
        else:
            with open(path, "wb") as file:
                file.write(data.last().__dict__[params.save_from_data].main)
            self._logger.debug("Data saved to %s", path)

        return data.last()

    def stream_call(
        self, data: AkariData, params: _SaveModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        return self.call(data, params, callback)
