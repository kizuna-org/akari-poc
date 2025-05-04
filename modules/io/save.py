import dataclasses
import time
import wave
from datetime import datetime
from typing import Any

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
            save_data = data.last().__dict__[params.save_from_data]
        except KeyError:
            raise ValueError(f"Data does not contain the key '{params.save_from_data}'.")
        if not save_data:
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
            audio_data: AkariDataSetType[bytes] = data.last().__dict__[params.save_from_data]
            meta: AkariDataSetType[dict[str, Any]] | None = data.last().meta
            with wave.open(path, "wb") as wav_file:
                wav_file.setnchannels(meta.main["channels"] if meta and "channels" in meta.main else 1)
                wav_file.setsampwidth(meta.main["sample_width"] if meta and "sample_width" in meta.main else 2)
                wav_file.setframerate(meta.main["rate"] if meta and "rate" in meta.main else 16000)
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
