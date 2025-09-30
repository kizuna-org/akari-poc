import dataclasses
from typing import Callable, Iterable

from vertexai.generative_models import Content, GenerativeModel

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)

_models: dict[str, GenerativeModel] = {}


@dataclasses.dataclass
class _LLMModuleParams:
    """Google Gemini 言語モデルを呼び出すために必要なパラメータを定義します。

    特定のモデル識別子（例: "gemini-pro"）と会話コンテンツが含まれます。
    会話コンテンツは直接提供することも、関数経由で生成することもできます。

    Attributes:
        model (str): 使用する Gemini モデルの識別子（例: "gemini-pro",
            "gemini-1.5-flash-latest"）。これにより、リクエストを処理する Gemini ファミリの
            どのバージョンかが決まります。
        messages (Optional[Iterable[Content]]): 会話履歴またはプロンプトを構成する
            `Content` オブジェクトのシーケンス。これは、`messages_function` が
            提供されていないか `None` を返す場合に使用されます。
        messages_function (Optional[Callable[[AkariData], Iterable[Content]]]):
            `AkariData` インスタンスを受け入れ、プロンプト用の `Content` オブジェクトの
            シーケンスを動的に生成する呼び出し可能オブジェクト。これにより、Akari パイプラインの
            以前のステップのデータに基づいて会話を構築できます。提供されている場合は、
            こちらが優先されます。デフォルトは `None` です。
    """

    model: str
    messages: Iterable[Content] | None = None
    messages_function: Callable[[AkariData], Iterable[Content]] | None = None


class _LLMModule(AkariModule):
    """Google の Gemini 大規模言語モデルへのインターフェースを提供します。

    構造化された会話履歴（`Content` オブジェクトのシーケンスとして）を
    指定された Gemini モデルに送信することで、コンテンツ生成を可能にします。
    同じモデルへの繰り返しの呼び出しを最適化するために、`GenerativeModel` インスタンスの
    ローカルキャッシュを管理します。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Gemini モデルと対話するための _LLMModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ベースモジュールの初期化に使用されます。
            logger (AkariLogger): 操作の詳細、デバッグ情報、API の相互作用を記録するための
                ロガーインスタンス。
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _LLMModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """指定された Google Gemini モデルにリクエストを送信して、テキストコンテンツを生成します。

        会話履歴（プロンプト）は、静的な `params.messages` から、または動的に
        `params.messages_function` 経由で決定されます。モジュールは、共有のインメモリキャッシュ
        （`_models`）を使用して、初期化された `GenerativeModel` インスタンスを格納および再利用し、
        同じモデルへの後続の呼び出しのパフォーマンスを向上させる可能性があります。
        モデルの応答から生成されたテキストは、その後 `AkariDataSet` にパッケージ化されます。

        Args:
            data (AkariData): 入力 `AkariData` オブジェクト。これは、プロンプトが
                以前のパイプラインの結果に基づいて動的に構築されるように、`params.messages_function` が
                設定されている場合に渡されます。
            params (_LLMModuleParams): ターゲットの Gemini モデル名と会話コンテンツ
                （直接または関数経由）を含むオブジェクト。
            callback (Optional[AkariModuleType]): オプションのコールバックモジュール。
                このパラメータは現在 Gemini LLMModule では使用されていません。

        Returns:
            AkariDataSet: 次のような `AkariDataSet`:
                - `text.main` には、Gemini モデルによって生成された主要なテキストコンテンツが含まれます。
                - `allData` には、`GenerativeModel.generate_content` メソッドによって返された
                  完全な生の応答オブジェクトが保持されます。

        Raises:
            ValueError: `params.messages` が `None` で、`params.messages_function` も
                `None` であるか `None` を返す場合。つまり、モデルに送信するメッセージコンテンツが
                利用できない場合。
            GoogleAPIError: 認証、ネットワークの問題、無効な API 使用法などの問題により、
                Gemini API への呼び出しが失敗した場合。（注: 具体的な例外タイプは
                `vertexai` ライブラリによって異なる場合があります）。
        """
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)

        if params.messages_function is not None:
            params.messages = params.messages_function(data)
        if params.messages is None:
            raise ValueError("Messages cannot be None. Please provide a valid list of messages.")

        if params.model not in _models:
            _models[params.model] = GenerativeModel(params.model)

        model = _models[params.model]
        response = model.generate_content(params.messages)

        dataset = AkariDataSet()
        dataset.text = AkariDataSetType(main=response.text)
        dataset.allData = response
        return dataset
