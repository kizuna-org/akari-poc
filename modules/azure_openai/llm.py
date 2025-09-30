import copy
import dataclasses
from typing import Callable, Iterable

from openai import AzureOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
)

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _LLMModuleParams:
    """Azure OpenAI Chat Completion API へのリクエストを設定します。

    ターゲットモデル、会話履歴（直接または関数経由）、および生成プロセスを制御する
    さまざまなパラメータ（創造性（temperature）、応答長（max_tokens）、
    ストリーミング動作など）を指定します。

    Attributes:
        model (str): チャット補完に使用する Azure OpenAI モデルの識別子
            （例: "gpt-4o-mini", "gpt-35-turbo"）。
        messages (Optional[Iterable[ChatCompletionMessageParam]]): 会話履歴を表す
            メッセージオブジェクトのシーケンス。各メッセージは
            `ChatCompletionMessageParam` 構造に準拠する必要があります。
            この属性は、`messages_function` が提供されていないか、None を返す場合に使用されます。
        messages_function (Optional[Callable[[AkariData], Iterable[ChatCompletionMessageParam]]]):
            `AkariData` インスタンスを受け入れ、`ChatCompletionMessageParam` オブジェクトの
            シーケンスを返す呼び出し可能オブジェクト。これにより、以前のパイプラインステップの
            データに基づいて会話履歴を動的に構築できます。提供されている場合、
            静的な `messages` 属性よりも優先されます。デフォルトは None です。
        temperature (float): 出力のランダム性を制御します。低い値（例: 0.2）は
            出力をより決定論的で集中的なものにし、高い値（例: 0.8）は
            よりランダムで創造的なものにします。0 から 2 の間でなければなりません。
            デフォルトは 1.0 です。
        max_tokens (int): チャット補完で生成するトークン（単語と句読点）の最大数。
            これにより、応答の長さが制限されます。デフォルトは 1024 です。
        top_p (float): ニュークリアスサンプリングを実装します。モデルは、上位 `top_p` の
            確率質量を構成するトークンのみを考慮します。値 0.1 は、上位 10% の
            確率分布のトークンのみが考慮されることを意味します。これは、
            温度ベースのサンプリングの代替手段です。デフォルトは 1.0 です。
        frequency_penalty (float): -2.0 から 2.0 の間の値。正の値は、
            生成されたテキスト内の既存の頻度に基づいてトークンにペナルティを課すことにより、
            モデルが逐語的に行を繰り返す可能性を減らします。デフォルトは 0.0 です。
        presence_penalty (float): -2.0 から 2.0 の間の値。正の値は、
            これまでのテキスト内での出現に基づいてトークンにペナルティを課すことにより、
            モデルが新しいトピックを導入することを奨励します。デフォルトは 0.0 です。
        stream (bool): True の場合、生成時に応答をチャンクでストリーミングバックするよう
            API に要求します。これには、これらのチャンクを処理するために `call` メソッドで
            `callback` モジュールを設定する必要があります。False の場合、
            生成が完了した後に完全な応答が受信されます。デフォルトは False です。
    """

    model: str
    messages: Iterable[ChatCompletionMessageParam] | None = None
    messages_function: Callable[[AkariData], Iterable[ChatCompletionMessageParam]] | None = None
    temperature: float = 1.0
    max_tokens: int = 1024
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False


class _LLMModule(AkariModule):
    """Azure OpenAI のチャット補完サービスと統合して、テキストベースの応答を生成します。

    AzureOpenAI クライアントを利用して、チャットプロンプト（メッセージのシーケンス）を
    指定された言語モデルに送信します。完全な応答のための標準的なブロッキングリクエストと、
    応答チャンクがコールバックモジュール経由で処理されるストリーミングリクエストの両方をサポートします。
    このモジュールは、受信した AkariData に基づいてメッセージ履歴を動的に構築できます。
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger, client: AzureOpenAI) -> None:
        """_LLMModule インスタンスを構築します。

        Args:
            router (AkariRouter): Akari ルーターインスタンス。ストリーミング操作中に
                コールバックモジュールを呼び出すために使用されます。
            logger (AkariLogger): 操作の詳細、デバッグ情報、API 応答を記録するための
                ロガーインスタンス。
            client (AzureOpenAI): `AzureOpenAI` クライアントの初期化済みインスタンス。
                API キーとエンドポイント情報で事前設定されています。
        """
        super().__init__(router, logger)
        self.client = client

    def call(self, data: AkariData, params: _LLMModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Azure OpenAI Chat Completion API にリクエストを送信し、応答を処理します。

        このメソッドは、`params.messages` から、または入力 `data` で `params.messages_function` を
        呼び出すことによって、会話履歴を決定します。
        その後、`client.chat.completions.create` を呼び出します。

        `params.stream` が True の場合:
            - `callback` モジュールを提供する必要があります。
            - メソッドは応答チャンクを反復処理します。コンテンツを含む各チャンクは、
              増加する `text_main` に追加され、`texts` のリストに追加されます。
              現在の `text_main` と `texts` のストリームを持つ `AkariDataSet` が作成され、
              ルーター経由で `callback` モジュールに非ブロッキング方式で送信されます
              （ただし、ルーター呼び出し自体はブロッキングである可能性があります）。
        `params.stream` が False の場合:
            - メソッドは完全な API 応答を待ちます。
            - 最初の選択肢のメッセージのコンテンツが `text_main` として抽出されます。

        どちらの場合も、結果の `text_main` と生の API 応答（ストリーミングの場合は最後のチャンク）が
        返される `AkariDataSet` に格納されます。

        Args:
            data (AkariData): 入力 `AkariData` オブジェクト。これは主に、
                API 呼び出しのメッセージのリストを動的に構築するために `params.messages_function` が
                設定されている場合に使用されます。
            params (_LLMModuleParams): モデル名、メッセージ、温度、ストリーミング設定など、
                API 呼び出しに必要なすべてのパラメータを含むオブジェクト。
            callback (Optional[AkariModuleType]): `params.stream` が True の場合に
                各応答チャンクで呼び出される Akari モジュールタイプ。このコールバックモジュールは、
                現在のストリーミング `AkariDataSet` で拡張された入力 `data` のコピーを受信します。

        Returns:
            AkariDataSet: 次のような `AkariDataSet`:
                - `text.main` には、生成された完全なテキストが含まれます。
                - `text.stream`（ストリーミングの場合）には、受信したテキストチャンクのリストが含まれます。
                - `allData` には、生の `ChatCompletion` オブジェクト（非ストリーミングの場合）または
                  最後の `ChatCompletionChunk` オブジェクト（ストリーミングの場合）が含まれます。

        Raises:
            ValueError: `params.stream` が True で `callback` が None の場合、または
                `params.messages` が None で `params.messages_function` も None のメッセージになる場合。
            TypeError: ストリーミングモードの API 応答チャンクが期待される構造
                （`choices`、`delta`、または `content` がない）に準拠していない場合、または
                非ストリーミング応答が `ChatCompletion` オブジェクトでない場合。
        """
        self._logger.debug("LLMModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)

        if params.stream and callback is None:
            raise ValueError("Callback must be provided when streaming is enabled.")

        if params.messages_function is not None:
            params.messages = params.messages_function(data)
        if params.messages is None:
            raise ValueError("Messages cannot be None. Please provide a valid list of messages.")

        response = self.client.chat.completions.create(
            model=params.model,
            messages=params.messages,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            top_p=params.top_p,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty,
            stream=params.stream,
        )

        dataset = AkariDataSet()
        text_main = ""
        if params.stream:
            texts: list[str] = []
            for chunk in response:
                if isinstance(chunk, ChatCompletionChunk) and hasattr(chunk, "choices"):
                    for choice in chunk.choices:
                        if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                            text_main += choice.delta.content if choice.delta.content else ""
                            if choice.delta.content is not None:
                                texts.append(choice.delta.content)
                            stream: AkariDataStreamType[str] = AkariDataStreamType(
                                delta=texts,
                            )
                            dataset.text = AkariDataSetType(main=text_main, stream=stream)
                            if callback is not None:
                                callData = copy.deepcopy(data)
                                callData.add(dataset)
                                self._router.callModule(
                                    moduleType=callback,
                                    data=callData,
                                    params=params,
                                    streaming=True,
                                )
                            else:
                                raise ValueError("Callback is None, but streaming is enabled.")
                        else:
                            raise TypeError("Chunk does not have 'delta' or 'content' attribute.")
                else:
                    raise TypeError("Chunk does not have 'choices' attribute or is improperly formatted.")
        else:
            if isinstance(response, ChatCompletion):
                self._logger.debug(response.choices[0].message.content)
                if response.choices[0].message.content:
                    text_main = response.choices[0].message.content
            else:
                raise TypeError("Response is not of type ChatCompletion.")

        dataset.text = AkariDataSetType(main=text_main)
        dataset.allData = response
        return dataset
