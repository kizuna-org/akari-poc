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
    """ファイルへのデータ保存設定を定義します。

    ターゲットファイルパス、データの取得元となる `AkariDataSet` 内のデータフィールド名、
    および一意性のためにファイル名にタイムスタンプを追加するかどうかを指定します。

    Attributes:
        file_path (str): データが保存される、目的のファイル名と拡張子を含む完全なパス。
        save_from_data (str): `.main` データコンテンツを保存用に取得する最後の
            `AkariDataSet` の属性名（例: "text"、"audio"、"meta"）。
            たとえば、"audio" の場合、`data.last().audio.main` を保存しようとします。
        with_timestamp (bool): `True` の場合、タイムスタンプ文字列（`YYYYMMDDHHMMSS` 形式）が
            ファイル拡張子の前にファイル名に挿入されます。たとえば、"output.wav" は
            "output_20231027143000.wav" のようになる場合があります。デフォルトは `False` です。
    """

    file_path: str
    save_from_data: str
    with_timestamp: bool = False


class _SaveModule(AkariModule):
    """Akari パイプラインのデータをファイルシステムに永続化します。

    パイプラインの最新の `AkariDataSet` から特定のデータフィールド
    （テキスト、オーディオバイト、メタデータなど）を指定されたファイルに保存できます。
    上書きを防ぐためのファイル名の自動タイムスタンプオプションと、
    提供されたメタデータに基づいて正しいヘッダー情報を保証するための WAV オーディオファイルの
    特別な処理が含まれています。
    """

    def __init__(
        self,
        router: AkariRouter,
        logger: AkariLogger,
    ) -> None:
        """_SaveModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ベースモジュールの初期化に使用されます。
            logger (AkariLogger): 保存成功パスや発生したエラーなどの操作の詳細を記録するための
                ロガーインスタンス。
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SaveModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """最新の `AkariDataSet` の指定されたフィールドからデータを抽出し、指定されたファイルパスに書き込みます。

        モジュールはまず、`AkariData` シーケンスの最後のデータセットから
        `params.save_from_data` で指定されたデータを取得しようとします。
        `params.with_timestamp` が true の場合、`params.file_path` を変更して
        現在のタイムスタンプを含め、保存されたファイルのバージョン管理に役立てます。

        オーディオデータには特別な処理が実装されています。`params.save_from_data` が "audio" で、
        `params.file_path` が ".wav" で終わる場合、モジュールは `data.last().meta` からの
        メタデータ（チャンネル、サンプル幅、レート）を使用して適切な WAV ファイルを書き込もうとします。
        このメタデータが不完全な場合は、適切なデフォルト値（1 チャンネル、2 バイトサンプル幅、
        16000 Hz レート）が使用されます。他のすべてのデータ型またはファイル拡張子の場合、
        データはバイナリモードで書き込まれます。

        Args:
            data (AkariData): パイプラインの現在の状態を含む `AkariData` オブジェクト。
                保存するデータは、その最後のデータセットから取得されます。
            params (_SaveModuleParams): ファイルパス、保存するデータフィールド、
                およびタイムスタンプを使用するかどうかを指定する設定。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在 SaveModule では使用されていません。

        Returns:
            AkariDataSet: 入力 `data` オブジェクトの最後の `AkariDataSet`。
            このモジュールはデータセット自体を変更しませんが、パイプラインフローを維持するために返します。

        Raises:
            ValueError: `params.save_from_data` が `data.last()` の有効なフィールドまたは
                移入されたフィールドに対応していない場合。
            IOError: アクセス許可、パスの問題などによりファイル書き込みが失敗した場合。
            wave.Error: 不正なオーディオパラメータまたはデータにより WAV ファイルの書き込みが失敗した場合。
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
        self, data: AkariData, params: _SaveModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        """非ストリーミング `call` メソッドとまったく同じように保存用のデータを処理します。

        このモジュールは、ストリーミングコールと非ストリーミングコールの個別のロジックを実装していません。
        どちらも同じファイル保存シーケンスを呼び出します。

        Args:
            data (AkariData): 保存するデータを含む `AkariData` オブジェクト。
            params (_SaveModuleParams): 保存操作の設定。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                現在は使用されていません。

        Returns:
            AkariDataSet: 入力 `data` の最後の `AkariDataSet`。
        """
        return self.call(data, params, callback)
