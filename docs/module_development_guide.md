# Akari 新規モジュール開発ガイド

## 導入

このガイドでは、Akariプロジェクトに新しい機能モジュールを追加する方法について説明します。モジュール開発の基本的な構造、作成手順、システムへの登録方法、および従うべき規約について解説します。

## モジュール構造

Akariの各機能モジュールは、`akari.module._AkariModule`クラスを継承して作成されます。基本的なモジュール構造は以下のようになります。

```python
import dataclasses
from typing import Any # 必要に応じて他の型もインポート

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType, # 必要に応じて他のAkariの型もインポート
    AkariLogger,
    AkariModule,
    AkariModuleParams, # モジュールがパラメータを取る場合
    AkariModuleType,
    AkariRouter,
)

# モジュールが固有のパラメータクラスを持つ場合
@dataclasses.dataclass
class _MyNewModuleParams(AkariModuleParams): # AkariModuleParamsを継承することが推奨されます
    param1: str
    param2: int = 0 # デフォルト値を持つパラメータ

class MyNewModule(_AkariModule): # _AkariModuleを継承します
    """
    （ここにモジュールの説明を記述します。日本語で記述してください。）

    Attributes:
        # （モジュールが持つ属性があれば記述します）
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """
        MyNewModuleインスタンスを構築します。

        Args:
            router (AkariRouter): Akariルーターインスタンス。
            logger (AkariLogger): ロガーインスタンス。
        """
        super().__init__(router, logger)
        # （モジュール固有の初期化処理があれば記述します）

    def call(
        self, data: AkariData, params: _MyNewModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet | AkariData: # 返り値の型は処理内容によります
        """
        （ブロッキング処理を行うcallメソッドの説明を記述します。）

        Args:
            data (AkariData): 入力データ。
            params (_MyNewModuleParams): モジュールパラメータ。
            callback (Optional[AkariModuleType]): コールバックモジュール（通常は使用されません）。

        Returns:
            AkariDataSet | AkariData: 処理結果。
        """
        self._logger.debug(f"{self.__class__.__name__} called")
        # --- ここにモジュールの主処理を記述します ---

        # 例: 入力データからテキストを取得し、処理して新しいデータセットを返す
        # input_text_dataset = data.last().text
        # if input_text_dataset and input_text_dataset.main:
        #     processed_text = input_text_dataset.main.upper()
        #     output_dataset = AkariDataSet()
        #     output_dataset.text = AkariDataSetType(main=processed_text)
        #     return output_dataset

        # パイプラインの次のモジュールにそのままデータを渡す場合
        # return data

        # 新しいデータセットを生成して返す場合
        new_dataset = AkariDataSet()
        # new_dataset.text = AkariDataSetType(main="新しいテキストデータ")
        # （必要に応じて他のデータ型も設定）
        return new_dataset

    def stream_call(
        self, data: AkariData, params: _MyNewModuleParams, callback: AkariModuleType | None = None
    ) -> AkariDataSet | AkariData:
        """
        （ストリーミング処理を行うstream_callメソッドの説明を記述します。）
        ストリーミングをサポートしない場合は、NotImplementedErrorを送出するか、callメソッドを呼び出します。

        Args:
            data (AkariData): 入力データ。
            params (_MyNewModuleParams): モジュールパラメータ。
            callback (Optional[AkariModuleType]): ストリーミング処理で中間結果を渡すコールバックモジュール。

        Returns:
            AkariDataSet | AkariData: 処理結果または最終結果。
        """
        self._logger.debug(f"{self.__class__.__name__} stream_call called")
        # ストリーミングをサポートしない場合:
        # raise NotImplementedError(f"{self.__class__.__name__} does not support streaming.")
        # または、ブロッキング呼び出しにフォールバック:
        return self.call(data, params, callback)

```

### 主要メソッド

*   **`__init__(self, router: AkariRouter, logger: AkariLogger)`**:
    *   モジュールのコンストラクタです。
    *   `super().__init__(router, logger)`を呼び出して親クラスの初期化を行います。
    *   モジュール固有の初期化処理（例: 外部ライブラリのクライアント設定）をここで行います。
*   **`call(self, data: AkariData, params: YourModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet | AkariData`**:
    *   モジュールの主要なブロッキング処理を実装します。
    *   入力として`AkariData`（これまでの処理結果のシーケンス）、`params`（モジュール固有のパラメータ）、`callback`（通常は`None`）を受け取ります。
    *   処理結果を`AkariDataSet`として生成し、それを返すか、あるいは入力`AkariData`を更新して返すことが一般的です。
    *   `data.last()`で直前のモジュールの処理結果（`AkariDataSet`）にアクセスできます。
*   **`stream_call(self, data: AkariData, params: YourModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet | AkariData`**:
    *   ストリーミング処理を実装する場合にオーバーライドします。
    *   データチャンクを継続的に処理し、中間結果を`callback`モジュール（指定されていれば）に`router.callModule`経由で渡すことができます。
    *   ストリーミングをサポートしないモジュールは、`NotImplementedError`を送出するか、`self.call(...)`を呼び出してブロッキング処理にフォールバックすることが推奨されます。

### パラメータクラス

*   モジュールが外部から設定可能なパラメータを持つ場合、`@dataclasses.dataclass`を用いてパラメータクラスを定義します。
*   慣例として、パラメータクラス名はモジュールクラス名の前にアンダースコアを付け、末尾に`Params`を付けます（例: `_MyNewModuleParams`）。
*   `akari.AkariModuleParams`を継承することが推奨されますが、必須ではありません。

## 新規モジュール作成手順

1.  **ファイル作成**:
    *   通常、`modules`ディレクトリ以下に、機能に応じたサブディレクトリを作成するか、既存のサブディレクトリ内に新しいPythonファイルを作成します（例: `modules/custom/my_new_module.py`）。
    *   ファイル名はモジュールの内容を表す簡潔な名前にします（例: `translator.py`, `image_processor.py`）。

2.  **モジュールクラス定義**:
    *   上記の「モジュール構造」セクションで示したテンプレートに従い、`_AkariModule`を継承した新しいクラスを定義します。
    *   クラス名はキャメルケースで、モジュールの機能を明確に示すものにします（例: `TextTranslatorModule`, `ImageOverlayModule`）。
    *   必要に応じて、パラメータクラス（例: `_TextTranslatorModuleParams`）も定義します。

3.  **`__init__`メソッド実装**:
    *   `super().__init__(router, logger)`を呼び出します。
    *   モジュールが必要とする初期設定（APIクライアントの初期化、デフォルト値の設定など）を行います。

4.  **`call`メソッド実装**:
    *   モジュールの中心となる処理ロジックを記述します。
    *   入力`data`（特に`data.last()`）から必要な情報を取得します。
    *   `params`を使用してモジュールの動作を調整します。
    *   処理結果を新しい`AkariDataSet`オブジェクトに格納します。
        *   `dataset = AkariDataSet()`
        *   `dataset.text = AkariDataSetType(main="処理済みテキスト")` のように、適切なデータ型フィールド（`text`, `audio`, `bool`, `meta`, `allData`）に結果をセットします。
    *   生成した`AkariDataSet`を返します。パイプラインによっては、入力`AkariData`オブジェクトにこの新しいデータセットを追加し、`AkariData`オブジェクト自体を返すこともあります。

5.  **`stream_call`メソッド実装（任意）**:
    *   モジュールがストリーミング処理（例: 音声認識のリアルタイム処理、大規模言語モデルの逐次応答）を行う場合に実装します。
    *   データチャンクを処理し、必要に応じて`callback`引数で指定されたモジュールを`self._router.callModule(...)`で呼び出し、中間結果を渡します。
    *   ストリーミングをサポートしない場合は、メソッドの先頭で`raise NotImplementedError(...)`とするか、`return self.call(data, params, callback)`としてブロッキング処理に委譲します。

6.  **`__init__.py`への登録（任意）**:
    *   作成したモジュールをサブディレクトリの`__init__.py`で公開すると、インポートが容易になります。
        ```python
        # modules/custom/__init__.py の例
        from .my_new_module import MyNewModule as MyNewModule
        from .my_new_module import _MyNewModuleParams as MyNewModuleParams # パラメータクラスも公開する場合

        __all__ = ["MyNewModule", "MyNewModuleParams"]
        ```
    *   さらに、ルートの`modules/__init__.py`でも公開することで、`from modules import MyNewModule`のようにアクセスできるようになります。

## モジュールのシステムへの登録

新しく作成したモジュールをAkariパイプラインで使用するには、アプリケーションのエントリーポイント（通常は`main.py`）でルーターに登録する必要があります。

1.  **モジュールのインポート**:
    ```python
    from modules.custom.my_new_module import MyNewModule, _MyNewModuleParams # __init__.pyで公開した場合
    # または直接 from modules.custom.my_new_module import MyNewModule, _MyNewModuleParams
    ```

2.  **モジュールのインスタンス化**:
    *   `__init__`メソッドで外部クライアント（例: `AzureOpenAI`クライアント）などが必要な場合は、事前に準備します。
    ```python
    # main.py 内
    # logger = ... (ロガーの取得)
    # router = AkariRouter(logger, router_options)
    # azure_openai_client = AzureOpenAI(...) # 例

    my_new_module_instance = MyNewModule(router, logger)
    # 外部クライアントが必要なモジュールの場合 (例: Azure TTS)
    # tts_module_instance = TTSModule(router, logger, azure_openai_client)
    ```

3.  **ルーターへの登録**:
    *   `AkariRouter`の`addModules`メソッドを使用して、モジュールタイプとそのインスタンスを辞書形式で登録します。
    ```python
    # main.py 内
    router.addModules(
        {
            # ... 他のモジュール ...
            MyNewModule: my_new_module_instance,
            # ...
        }
    )
    ```

4.  **パイプラインでの使用**:
    *   登録後、`_RootModule`や`_SerialModule`のパラメータとして、他のモジュールと同様に新しいモジュールタイプを指定してパイプラインに組み込むことができます。
    ```python
    # main.py 内の _SerialModuleParams の例
    serial_params = _SerialModuleParams(
        modules=[
            # ... 他の処理ステップ ...
            _SerialModuleParamModule(
                moduleType=MyNewModule,
                moduleParams=_MyNewModuleParams(param1="value1", param2=123),
                moduleCallback=None # 必要に応じてコールバックも指定
            ),
            # ... 他の処理ステップ ...
        ]
    )
    # root_module.call(initial_data, _SerialModule, serial_params) のように使用
    ```

## 規約

*   **命名規則**:
    *   モジュールクラス名: アンダースコアで始まるキャメルケース（例: `_MyExampleModule`）。Akariフレームワーク内部で使用されることを意図しているため、慣例的にアンダースコアで始めます。ただし、アプリケーション開発者が直接利用するモジュールとして設計する場合は、アンダースコアなしのキャメルケース（例: `MyPublicModule`）も許容されます。
    *   パラメータクラス名: アンダースコアで始まるモジュールクラス名に`Params`を付与（例: `_MyExampleModuleParams`）。
    *   ファイル名: スネークケース（例: `my_example_module.py`）。
*   **Docstring**:
    *   すべてのクラス、メソッドには、その機能、引数、返り値などを説明するdocstringを記述してください（日本語推奨）。
    *   クラスのdocstringには、モジュールの概要と、必要であれば`Attributes:`セクションを設けてください。
    *   メソッドのdocstringには、`Args:`, `Returns:`, `Raises:`（該当する場合）セクションを設けてください。
*   **ロギング**:
    *   モジュールの動作状況や重要なステップ、エラー情報などを`self._logger`を通じて記録してください。
    *   `self._logger.debug(...)`、`self._logger.info(...)`、`self._logger.warning(...)`、`self._logger.error(...)`を適切に使い分けてください。
*   **型ヒント**:
    *   コードの可読性と保守性を高めるため、型ヒントを積極的に使用してください。
*   **`AkariData`の不変性**:
    *   原則として、モジュールは入力された`AkariData`オブジェクトを直接変更せず、新しい`AkariDataSet`を生成して返すか、`AkariData`のコピーに変更を加えるようにします。ただし、パフォーマンス上の理由や設計上の意図がある場合はこの限りではありません。
*   **エラーハンドリング**:
    *   予期されるエラー（例: API呼び出しの失敗、不正な入力データ）に対しては、適切な例外処理を行い、必要に応じてエラー情報をログに記録してください。

このガイドに従うことで、Akariプロジェクトへの新しいモジュールの追加がスムーズに行えるようになります。
