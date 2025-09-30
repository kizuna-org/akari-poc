import dataclasses
import io
import wave

from openai import AzureOpenAI

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
class _STTModuleParams:
    """Azure OpenAI STT サービスへの音声文字起こしリクエストの設定を指定します。

    詳細には、使用する AI モデル、精度向上のための言語ヒント、文脈プロンプト、
    ランダム性を制御するための温度、入力オーディオストリームの物理的特性が含まれます。

    Attributes:
        model (str): 文字起こしに使用する Azure OpenAI STT モデルの識別子
            （例: "whisper-1"）。
        language (Optional[str]): 音声で話されている言語の ISO-639-1 コード
            （例: 英語の場合は "en"、日本語の場合は "ja"）。これを提供すると、
            文字起こしの精度が向上し、レイテンシが短縮される可能性があります。`None` の場合、
            サービスは言語を自動検出する場合があります。
        prompt (Optional[str]): 文字起こしモデルをガイドするために使用できるテキストプロンプト。
            特定の用語、名前、スタイルの精度を向上させたり、以前のオーディオセグメントからの
            コンテキストを提供したりする可能性があります。プロンプトはオーディオと同じ言語である必要があります。
        temperature (float): 文字起こしプロセスのランダム性を制御し、
            代替手段が存在する場合の単語の選択に影響を与えます。値は通常 0 から 1 の間です。
            低い値（例: 0.2）は、より決定論的で一般的な結果を生成し、高い値（例: 0.8）は、
            より多様ですが、潜在的に精度の低い出力を生成します。
        channels (int): 入力オーディオデータに存在するオーディオチャンネルの数
            （例: モノラルの場合は 1、ステレオの場合は 2）。この情報は、生のオーディオバイトを
            正しく解釈するために不可欠です。デフォルトは 1（モノラル）です。
        sample_width (int): 各オーディオサンプルのバイト単位のサイズ
            （例: 16 ビットオーディオの場合は 2、8 ビットオーディオの場合は 1）。
            これは、`channels` および `rate` とともにオーディオ形式を定義します。
            デフォルトは 2（16 ビット）です。
        rate (int): ヘルツ単位（サンプル/秒）の入力オーディオのサンプリングレート
            （またはフレームレート）。16000、24000、44100 など。これは、
            オーディオデータの実際のサンプルレートと一致する必要があります。
            デフォルトは 24000 Hz です。
    """

    model: str
    language: str | None
    prompt: str | None
    temperature: float
    channels: int = 1
    sample_width: int = 2
    rate: int = 24000


class _STTModule(AkariModule):
    """Azure OpenAI の音声認識機能を活用して、音声からテキストへの文字起こしを実行します。

    AkariDataSet から生のオーディオデータ（PCM バイトとして期待される）を取得し、
    それをメモリ内バッファの WAV 形式にカプセル化し、その後このオーディオを
    設定された Azure OpenAI STT モデルに送信して文字起こしを行います。
    結果のテキストは、その後 AkariDataSet に戻されます。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """_STTModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ベースモジュールの初期化に使用されます。
            logger (AkariLogger): 操作の詳細とデバッグ情報を記録するためのロガーインスタンス。
            client (AzureOpenAI): `AzureOpenAI` クライアントの初期化済みインスタンス。
                音声認識サービスへのアクセス用に事前設定されています。
        """
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _STTModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """設定された Azure OpenAI STT モデルを使用して、生の PCM データとして提供された話し言葉の音声を書き言葉のテキストに変換します。

        このメソッドは、オーディオデータが `data.last().audio.main` に存在することを期待します。
        このデータは、その後、メモリ内バッファの WAV オーディオ形式にラップされます。
        この WAV データは、その後 Azure OpenAI オーディオ文字起こし API に送信されます。
        文字起こしの結果（プレーンテキストとして）は、その後新しい `AkariDataSet` に格納されます。

        Args:
            data (AkariData): 入力オーディオを含む `AkariData` オブジェクト。
                オーディオバイトは `data.last().audio.main` にあることが期待されます。
            params (_STTModuleParams): STT モデル名、言語、プロンプト、温度、
                オーディオプロパティ（チャンネル、サンプル幅、レート）など、文字起こしの設定パラメータ。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在 STTModule では使用されていません。

        Returns:
            AkariDataSet: 次のような `AkariDataSet`:
                - `text.main` には、文字起こしされたテキストが文字列として含まれます。
                - `allData` には、Azure OpenAI API からの生の応答オブジェクトが保持されます。

        Raises:
            ValueError: `data.last().audio` が None であるか、オーディオデータが含まれていない場合。
            OpenAIError: Azure OpenAI API 呼び出しが何らかの理由で失敗した場合
                （例: 認証、ネットワークの問題、無効なパラメータ）。
        """
        self._logger.debug("STTModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        audio = data.last().audio
        if audio is None:
            raise ValueError("Audio data is missing or empty.")

        pcm_buffer = io.BytesIO(audio.main)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(params.channels)
            wav_file.setsampwidth(params.sample_width)
            wav_file.setframerate(params.rate)
            wav_file.writeframes(pcm_buffer.read())

        wav_buffer.seek(0)
        wav_buffer.name = "input.wav"

        response = self.client.audio.transcriptions.create(
            model=params.model,
            file=wav_buffer,
            language=params.language if params.language else "",
            prompt=params.prompt if params.prompt else "",
            response_format="text",
            temperature=params.temperature,
        )

        text_main = str(response)

        dataset = AkariDataSet()
        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
