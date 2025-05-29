import dataclasses
import wave
from datetime import datetime
from typing import Any

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SaveModuleParams:
    """Defines the configuration for saving data to a file.

    Specifies the target file path, the name of the data field within an
    `AkariDataSet` to source the data from, and whether to append a
    timestamp to the filename for uniqueness.

    Attributes:
        file_path (str): The complete path, including the desired filename and
            extension, where the data will be saved.
        save_from_data (str): The attribute name (e.g., "text", "audio", "meta")
            on the last `AkariDataSet` from which the `.main` data content should
            be retrieved for saving. For instance, if "audio", it will attempt
            to save `data.last().audio.main`.
        with_timestamp (bool): If `True`, a timestamp string (formatted as
            `YYYYMMDDHHMMSS`) will be inserted into the filename before the
            file extension. For example, "output.wav" might become
            "output_20231027143000.wav". Defaults to `False`.
    """

    file_path: str
    save_from_data: str
    with_timestamp: bool = False


class _SaveModule(AkariModule):
    """Persists data from an Akari pipeline to the filesystem.

    Enables saving of specific data fields (like text, audio bytes, or metadata)
    from the most recent `AkariDataSet` in the pipeline to a designated file.
    It includes options for automatic timestamping of filenames to prevent
    overwrites and special handling for WAV audio files to ensure correct
    header information based on provided metadata.
    """

    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        """Constructs a _SaveModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for base module
                initialization.
            logger (AkariLogger): The logger instance for recording operational
                details, such as successful save paths or errors encountered.
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SaveModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Extracts data from a designated field in the most recent `AkariDataSet` and writes it to a specified file path.

        The module first attempts to retrieve the data specified by
        `params.save_from_data` from the last dataset in the `AkariData` sequence.
        If `params.with_timestamp` is true, it modifies the `params.file_path`
        to include a current timestamp, helping to version saved files.

        Special handling is implemented for audio data: if `params.save_from_data`
        is "audio" and `params.file_path` ends with ".wav", the module attempts
        to write a proper WAV file using metadata (channels, sample width, rate)
        from `data.last().meta`. If this metadata is incomplete, it uses sensible
        defaults (1 channel, 2 bytes sample width, 16000 Hz rate).
        For all other data types or file extensions, the data is written in binary mode.

        Args:
            data (AkariData): The `AkariData` object containing the pipeline's
                current state. The data to be saved is sourced from its last dataset.
            params (_SaveModuleParams): Configuration specifying the file path,
                the data field to save, and whether to use a timestamp.
            callback (Optional[AkariModuleType]): An optional callback module. This
                parameter is currently not used by the SaveModule.

        Returns:
            AkariDataSet: The last `AkariDataSet` from the input `data` object.
            This module does not modify the dataset itself but returns it to
            maintain pipeline flow.

        Raises:
            ValueError: If `params.save_from_data` does not correspond to a valid
                or populated field in `data.last()`.
            IOError: If file writing fails due to permissions, path issues, etc.
            wave.Error: If writing a WAV file fails due to incorrect audio
                parameters or data.
        """
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
        self,
        data: AkariData,
        params: _SaveModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Processes data for saving identically to the non-streaming `call` method.

        This module does not implement distinct logic for streaming versus
        non-streaming calls. Both invoke the same file-saving sequence.

        Args:
            data (AkariData): The `AkariData` object containing the data to save.
            params (_SaveModuleParams): Configuration for the save operation.
            callback (Optional[AkariModuleType]): An optional callback module,
                currently unused.

        Returns:
            AkariDataSet: The last `AkariDataSet` from the input `data`.
        """
        return self.call(data, params, callback)
