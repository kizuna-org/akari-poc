from __future__ import annotations

import dataclasses
import datetime
import wave
from pathlib import Path

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SaveModuleParams(AkariModuleParams):
    """SaveModuleのパラメータ."""

    file_path: str
    """保存先のファイルパス."""
    save_from_data: str
    """AkariDataから保存するデータのキー."""
    with_timestamp: bool = False
    """ファイル名にタイムスタンプを追加するかどうか. デフォルトはFalse."""
    ensure_dir: bool = False
    """保存先のディレクトリが存在しない場合に作成するかどうか. デフォルトはFalse."""


class _SaveModule(AkariModule):
    """AkariDataSet内の指定されたデータをファイルに保存するモジュール."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)
        self._logger = logger

    def call(
        self,
        data: AkariData,
        params: _SaveModuleParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Extract data from a designated field and save it to a file.

        The module first attempts to retrieve the data specified by
        `params.save_from_data` from the `main` attribute of the last
        `AkariDataSet` in the provided `AkariData` object. If the data is not found,
        a `ValueError` is raised.

        Args:
            data: AkariData object containing the data to save.
            params: _SaveModuleParams object specifying the file path and data key.
            _callback: Unused callback module type.

        Returns:
            An empty AkariDataSet upon successful saving.

        Raises:
            ValueError: If the specified data key is not found in the AkariData or the data is empty.
            IOError: If there is an error writing to the file.
        """
        try:
            # Attempt to get data from data.last().attribute
            save_data = getattr(data.last(), params.save_from_data)
            if hasattr(save_data, "main"):
                save_data = save_data.main
            elif hasattr(save_data, "stream"):
                save_data = save_data.stream.last() if save_data.stream else None

        except AttributeError:
            # TRY003, EM102: Assign exception message to variable
            error_msg = f"Data does not contain the attribute '{params.save_from_data}'."
            raise ValueError(error_msg) from None

        if not save_data:
            # TRY003, EM102: Assign exception message to variable
            error_msg = f"Data does not contain the attribute '{params.save_from_data}' or it is empty."
            raise ValueError(error_msg) from None

        path_str = params.file_path
        if params.with_timestamp:
            paths = path_str.rsplit(".", 1)
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
            # SIM108: Use ternary operator
            path_str = f"{paths[0]}_{timestamp}.{paths[1]}" if len(paths) > 1 else f"{path_str}_{timestamp}"
        path = Path(path_str)
        if params.ensure_dir:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._logger.debug("Ensured directory exists: %s", path.parent)

        try:
            if path_str.endswith(".wav") and params.save_from_data == "audio" and isinstance(save_data, bytes):
                # Assuming save_data is bytes for WAV
                with wave.open(str(path), "wb") as wf:
                    wf.setnchannels(1)  # Mono
                    wf.setsampwidth(2)  # 16 bits
                    wf.setframerate(16000)  # Assume 16KHz, ideally from metadata
                    wf.writeframes(save_data)
                self._logger.debug("Audio data saved as WAV to %s", path)
            elif isinstance(save_data, (str, bytes)):
                mode = "w" if isinstance(save_data, str) else "wb"
                encoding = "utf-8" if isinstance(save_data, str) else None
                with path.open(mode, encoding=encoding) as file:
                    file.write(save_data)
                self._logger.debug("Data saved to %s", path)
            else:
                # TRY003, EM102: Assign exception message to variable
                error_msg = f"Unsupported data type for saving: {type(save_data)}. "
                raise TypeError(error_msg) from None

        except OSError as e:
            self._logger.exception("Error writing to file %s: %s", path, e)  # noqa: TRY401
            # TRY003: Avoid specifying long messages outside the exception class
            # EM102: Exception must not use an f-string literal, assign to variable first
            # No TRY401 here as 'e' is used in the message directly.
            error_text = f"Error saving data to {path}: {e!s}"
            raise OSError(error_text) from e

        return AkariDataSet()

    def stream_call(
        self,
        data: AkariData,
        params: _SaveModuleParams,
        _callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Processes data for saving identically to the non-streaming `call` method.

        This module does not differentiate between streaming and non-streaming
        data for the save operation, processing it as a single data point.

        Args:
            data: AkariData object containing the data to save.
            params: _SaveModuleParams object specifying the file path and data key.
            _callback: Unused callback module type.

        Returns:
            An empty AkariDataSet upon successful saving.
        """
        return self.call(data, params, _callback)
