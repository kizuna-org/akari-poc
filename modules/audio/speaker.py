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
    """スピーカー経由の音声再生設定を定義します。

    音声形式（サンプルタイプ、レート、チャンネル）、使用する特定の出力デバイス、
    再生用のバッファリングパラメータなどの設定が含まれます。

    Attributes:
        format (int): 音声サンプルの PyAudio 形式定数（例: 16 ビット符号付き整数の場合は
            `pyaudio.paInt16`）。これにより、各音声サンプルのビット深度とタイプが決まります。
            デフォルトは `pyaudio.paInt16` です。
        rate (Optional[int]): 再生用の目的のサンプリングレート（ヘルツ単位、サンプル/秒）。
            `None` に設定すると、モジュールは入力音声のメタデータからレートを導き出そうとします。
            デフォルトは `None` です。
        channels (Optional[int]): オーディオチャンネルの数（例: モノラルは 1、ステレオは 2）。
            `None` の場合、モジュールは入力音声のメタデータからこれを取得しようとします。
            デフォルトは `None` です。
        chunk (int): 入力バッファから読み取り、一度に出力ストリームに書き込むオーディオフレームの数。
            これは再生のレイテンシと滑らかさに影響を与える可能性があります。デフォルトは 1024 フレームです。
        output_device_index (Optional[int]): 再生に使用するオーディオ出力デバイスの数値インデックス。
            `None` の場合、PyAudio のデフォルト出力デバイスが選択されます。デフォルトは `None` です。
    """

    format: int = pyaudio.paInt16
    rate: int | None = None
    channels: int | None = None
    chunk: int = 1024
    output_device_index: int | None = None


class _SpeakerModule(AkariModule):
    """システムのスピーカーまたは選択されたオーディオ出力デバイスを介した音声再生を容易にします。

    `AkariDataSet` からオーディオデータを取得し、再生パラメータ（サンプルレートやチャンネルなど）に
    関連するメタデータを使用する可能性があります。その後、PyAudio ライブラリを使用して、
    このデータを目的のオーディオ出力にストリーミングします。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """SpeakerModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ベースモジュールの初期化に使用されます
                （ただし、再生ロジックには直接使用されません）。
            logger (AkariLogger): 再生エラーや情報メッセージなどの操作の詳細を記録するための
                ロガーインスタンス。
        """
        super().__init__(router, logger)

    def _play(self, buffer: io.BytesIO, params: _SpeakerModuleParams, channels: int, rate: int) -> None:
        """PyAudio を使用して低レベルのオーディオ再生を処理します。

        提供されたパラメータで設定された PyAudio 出力ストリームを開きます。
        次に、`buffer` からチャンク単位でオーディオデータを読み取り、バッファがなくなるまで
        これらのチャンクをストリームに書き込みます。再生後に PyAudio リソースが
        適切に解放されるようにします。

        Args:
            buffer (io.BytesIO): 再生する生のオーディオデータを含むバイトストリーム。
            params (_SpeakerModuleParams): 形式、チャンクサイズ、出力デバイスインデックスなどの
                再生設定。
            channels (int): オーディオデータのチャンネル数。
            rate (int): オーディオデータのサンプリングレート（Hz 単位）。
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
        """AkariData オブジェクトからオーディオデータと重要な再生パラメータを抽出して検証します。

        このメソッドは、提供された `AkariData` の最後の `AkariDataSet` から
        オーディオコンテンツ（バイトとして）を取得しようとします。また、チャンネル数と
        サンプリングレートを決定し、`params` で明示的に設定された値を優先し、
        利用可能な場合は `AkariDataSet` 内に格納されているメタデータにフォールバックします。

        Args:
            data (AkariData): オーディオを抽出する `AkariData` インスタンス。
                オーディオは `data.last().audio` に、メタデータは `data.last().meta` に
                あることが期待されます。
            params (_SpeakerModuleParams): チャンネルやレートなどの不足している
                オーディオプロパティをオーバーライドまたは提供する可能性のある設定パラメータ。

        Returns:
            tuple[io.BytesIO, int, int]: 最初の要素がオーディオデータを含む
            `io.BytesIO` バッファ、2番目の要素がチャンネル数、3番目の要素が
            サンプリングレートであるタプル。

        Raises:
            ValueError: オーディオデータフィールド（`data.last().audio`）が見つからないか空の場合、
                またはチャンネル数やサンプリングレートを `params` またはオーディオメタデータから
                特定できない場合。
        """
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
        """AkariData シーケンスの最新のデータセットに含まれるオーディオデータの再生を調整します。

        このメソッドは最初に `_prepare_audio` を呼び出してオーディオバイトを抽出し、
        必要な再生パラメータ（チャンネル、レート）を決定します。次に、`_play` メソッドを
        呼び出して実際のオーディオ出力を実行します。

        Args:
            data (AkariData): オーディオデータを含む `AkariData` オブジェクト。
                通常、最後の `AkariDataSet` の `audio` フィールドにあります。
            params (_SpeakerModuleParams): 出力デバイス、オーディオ形式などの再生用の
                設定パラメータ。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在 SpeakerModule では使用されていません。

        Returns:
            AkariDataSet: モジュールの主な効果はオーディオ出力であり、データの変換や生成ではないため、
            空の `AkariDataSet`。
        """
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        dataset = AkariDataSet()
        return dataset

    def stream_call(
        self, data: AkariData, params: _SpeakerModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet:
        """非ストリーミング `call` メソッドとまったく同じように再生用のオーディオデータを処理します。

        このモジュールは、ストリーミングコールと非ストリーミングコールの個別のロジックを実装していません。
        どちらも同じオーディオ準備と再生シーケンスを呼び出します。

        Args:
            data (AkariData): オーディオを含む `AkariData` オブジェクト。
            params (_SpeakerModuleParams): 再生設定パラメータ。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                現在は使用されていません。

        Returns:
            AkariDataSet: 空の `AkariDataSet`。
        """
        buffer, channels, rate = self._prepare_audio(data, params)
        self._play(buffer, params, channels, rate)

        dataset = AkariDataSet()
        return dataset
