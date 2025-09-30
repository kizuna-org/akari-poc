import dataclasses

from openai import AzureOpenAI
from typing_extensions import Literal

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
class _TTSModuleParams:
    """Azure OpenAI Text-to-Speech (TTS) API へのリクエストを設定します。

    音声モデル、目的のオーディオ出力形式、話速、および合成プロセスをガイドするための
    特定の指示（例: 感情的なトーン）を指定します。

    Attributes:
        model (str): 音声合成に使用する Azure OpenAI TTS モデルの識別子
            （例: "tts-1", "tts-1-hd"）。
        voice (str): オーディオの生成に使用する事前定義された音声の名前。
            利用可能な音声には、"alloy"、"echo"、"fable"、"onyx"、"nova"、"shimmer" があります。
        instructions (Optional[str]): 合成された音声のスタイル、トーン、または配信に影響を与えるために
            TTS モデルに提供されるテキストガイダンス。例: 「穏やかで安心感のあるトーンで話してください。」
        response_format (Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]):
            出力オーディオの目的のファイル形式。サポートされている形式には、MP3、Opus
            （インターネットストリーミング用）、AAC（デジタルオーディオ圧縮用）、FLAC（可逆）、
            WAV（非圧縮）、PCM（生のパルス符号変調）が含まれます。デフォルトは "pcm" です。
        speed (float): 合成された音声の速度を制御します。値は 0.25（1/4 倍速）から
            4.0（4 倍速）の範囲です。値 1.0 は通常の速度を表します。デフォルトは 1.0 です。
    """

    model: str
    voice: str
    instructions: str | None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "pcm"
    speed: float = 1.0


class _TTSModule(AkariModule):
    """Azure OpenAI の Text-to-Speech (TTS) 機能と連携して、テキスト入力から音声スピーチを生成します。

    このモジュールは `AkariDataSet` 経由でテキストを受け入れ、AzureOpenAI クライアントを利用して
    音声合成を要求します。結果のオーディオデータは、その後 `AkariDataSet` にパッケージ化されて戻されます。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """_TTSModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ベースモジュールの初期化に使用されます。
            logger (AkariLogger): 操作の詳細とデバッグ情報を記録するためのロガーインスタンス。
            client (AzureOpenAI): `AzureOpenAI` クライアントの初期化済みインスタンス。
                テキスト読み上げサービスへのアクセス用に事前設定されています。
        """
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _TTSModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Azure OpenAI TTS API にテキストを送信し、合成されたオーディオデータを受信します。

        入力テキストは `data.last().text.main` から取得されます。このテキストは、
        指定されたモデル、音声、およびその他のパラメータとともに Azure OpenAI
        `audio.speech.create` エンドポイントに送信されます。応答からのバイナリオーディオコンテンツが
        読み取られ、新しい `AkariDataSet` に格納されます。PCM 形式の場合、デフォルトのオーディオメタデータ
        （チャンネル: 1、レート: 24000）が想定されます。他の形式の場合、このメタデータは
        外部解釈が必要になる場合があります。

        Args:
            data (AkariData): 入力テキストを取得する `AkariData` オブジェクト。
                `data.last().text.main` にあることが期待されます。
            params (_TTSModuleParams): モデル、音声、応答形式、話速など、
                TTS リクエストの設定パラメータ。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在 TTSModule では使用されていません。

        Returns:
            AkariDataSet: 次のような `AkariDataSet`:
                - `audio.main` には、合成されたオーディオの生のバイトが含まれます。
                - `meta.main` には、デフォルトの "channels" (1) と "rate" (24000) を持つ辞書が含まれ、
                  主に PCM に関連します。
                - `allData` には、Azure OpenAI API からの生の応答オブジェクトが保持されます。

        Raises:
            ValueError: `data.last().text` が None であるか、テキストが含まれていない場合。
            OpenAIError: Azure OpenAI API 呼び出しが失敗した場合（例: 認証、
                ネットワークの問題、無効なパラメータ）。
        """
        self._logger.debug("TTSModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        input_data = data.last().text
        if input_data is None:
            raise ValueError("Input data is missing or empty.")

        response = self.client.audio.speech.create(
            model=params.model,
            input=input_data.main,
            voice=params.voice,
            instructions=params.instructions if params.instructions else "",
            response_format=params.response_format,
            speed=params.speed,
        )

        dataset = AkariDataSet()
        dataset.audio = AkariDataSetType(main=response.read())
        dataset.meta = AkariDataSetType(main={"channels": 1, "rate": 24000})
        dataset.allData = response
        return dataset
