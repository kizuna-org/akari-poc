# Akari モジュール作成ガイド

Akari モジュールは、Akari フレームワーク内の基本的な処理単位です。このガイドでは、独自のカスタムモジュールを作成し、Python の慣習に従って適切に公開する方法について概説します。

**コアコンセプト**

モジュールを作成する前に、これらの主要コンポーネントを理解することが重要です。

- **AkariModule**: すべての Akari モジュールが継承する必要のある抽象基底クラスです。モジュールの基本的な構造（初期化、標準操作およびストリーミング操作のメソッドなど）を定義します。
- **AkariData**: データセットのシーケンスを調整し、処理パイプラインを通るデータの状態とフローを表します。モジュールは AkariData インスタンスを受け取り、以前のデータセットを検査し、新しい AkariDataSet インスタンスを追加できます。
- **AkariDataSet**: 単一のモジュール実行によって生成されたさまざまなデータ型（テキスト、音声、ブール値、メタデータ）を、モジュール実行に関するメタデータとともに集約します。
- **AkariRouter**: Akari モジュールの実行を管理します。利用可能なモジュールのレジストリを保持し、データフロー、パラメータ渡し、ロギングを処理しながら、それらに呼び出しをディスパッチします。
- **AkariLogger**: Akari フレームワーク内で使用するためのカスタマイズされたロガーインスタンスです。

**カスタムモジュールの作成**

カスタム Akari モジュールを作成するには、次の手順に従います。

1.  **モジュールクラスの定義 (プライベート)**
    `akari.AkariModule` を継承する新しい Python クラスを、アンダースコアで始まるプライベート名（例: `_MyCustomModule`）で作成します。

    ```python
    #例: modules/custom/_my_custom_module.py

    from akari import (
        AkariData,
        AkariDataSet,
        AkariDataSetType, # AkariDataSetType をインポート
        AkariDataStreamType, # AkariDataStreamType をインポート (ストリームデータ用)
        AkariLogger,
        AkariModule,
        AkariModuleParams, # またはパラメータ用のカスタムデータクラス
        AkariModuleType,
        AkariRouter,
    )
    import dataclasses # パラメータクラス用に dataclasses をインポート
    from typing import Any # メタデータ用に Any をインポート

    # モジュール固有のパラメータを定義（オプション、プライベート名で）
    @dataclasses.dataclass
    class _MyCustomModuleParams(AkariModuleParams): # AkariModuleParams を継承
        my_setting_1: str
        my_setting_2: int = 10
        sample_rate: int = 16000 # 音声処理用のサンプルレートなど

    class _MyCustomModule(AkariModule): # プライベート名で定義
        # ... (以降の実装)
    ```

2.  **モジュールの初期化**
    `__init__`メソッドを実装します。これは `router: AkariRouter` と `logger: AkariLogger` を引数として受け入れ、`super().__init__(router, logger)`を使用して親クラスの`__init__`メソッドに渡す必要があります。モジュールが必要とする可能性のある他の属性も初期化できます。

    ```python
    # modules/custom/_my_custom_module.py 内
    class _MyCustomModule(AkariModule):
        def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
            super().__init__(router, logger)
            # ここにカスタム初期化を記述
            self._logger.info("_MyCustomModule initialized")
    ```

3.  **`call` メソッドの実装**
    `call` メソッドは、非ストリーミング操作のためのモジュールの主要なロジックが存在する場所です。これは `AkariModule` の抽象メソッドであるため、実装する必要があります。

    **パラメータ:**

    - `data: akari.AkariData`: 入力データオブジェクト。以前のモジュールからの結果を含む可能性があります。
    - `params: AkariModuleParams`（またはカスタムデータクラス）: その動作を構成するモジュール固有のパラメータ。ここでは先ほど定義した `_MyCustomModuleParams` を使用します。
    - `callback: AkariModuleType | None = None`: オプションのコールバックモジュールタイプ。

    **戻り値:**

    モジュールが単一の結果セットを生成する場合は `akari.AkariDataSet` インスタンス、または全体的なデータパイプラインを変更したり複数のデータセットを生成したりする場合は `akari.AkariData` インスタンスのいずれかを返す必要があります。

    ```python
    # modules/custom/_my_custom_module.py 内
    class _MyCustomModule(AkariModule):
        # ... (__init__ は省略)

        def call(
            self,
            data: AkariData,
            params: _MyCustomModuleParams, # 具体的なParamsデータクラス (_MyCustomModuleParams) に置き換えます
            callback: AkariModuleType | None = None
        ) -> AkariDataSet | AkariData:
            self._logger.debug(f"_MyCustomModule 'call' invoked with data: {data}, params: {params}")

            # --- ここにモジュールのロジックを記述 ---
            # 例: 最後のデータセットからテキストと音声データにアクセス
            input_text = "Default"
            input_audio_bytes: bytes | None = None
            audio_meta: dict[str, Any] | None = None

            if data.datasets: # data.datasetsが空でないことを確認
                last_dataset = data.last()
                if last_dataset.text: # last_dataset.textがNoneでないことを確認
                    input_text = last_dataset.text.main
                if last_dataset.audio: # last_dataset.audioがNoneでないことを確認
                    input_audio_bytes = last_dataset.audio.main
                if last_dataset.meta: # last_dataset.metaがNoneでないことを確認
                    audio_meta = last_dataset.meta.main
                    self._logger.info(f"Input audio metadata: {audio_meta}")

            # 結果用の新しいデータセットを作成
            result_dataset = AkariDataSet()
            result_dataset.text = AkariDataSetType(main=f"Processed: {input_text} with param1: {params.my_setting_1}, param2: {params.my_setting_2}")

            if input_audio_bytes:
                processed_audio_bytes = input_audio_bytes # ここで実際の処理を行う
                result_dataset.audio = AkariDataSetType(main=processed_audio_bytes)
                result_dataset.meta = AkariDataSetType(main={
                    "processed": True,
                    "original_sample_rate": audio_meta.get("rate") if audio_meta else params.sample_rate,
                    "new_sample_rate": params.sample_rate,
                    "channels": audio_meta.get("channels") if audio_meta else 1,
                })
            else:
                result_dataset.meta = AkariDataSetType(main={"message": "No input audio data."})

            return result_dataset
            # または、AkariDataオブジェクトをより広範囲に変更する場合:
            # data.add(result_dataset)
            # return data
    ```

4.  **(オプション) `stream_call` メソッドの実装**
    モジュールがストリーミング操作をサポートする必要がある場合は、`stream_call` メソッドをオーバーライドします。

    ```python
    # modules/custom/_my_custom_module.py 内
    class _MyCustomModule(AkariModule):
        # ... (__init__, call は省略)

        def stream_call(
            self,
            data: AkariData,
            params: _MyCustomModuleParams, # 具体的なParamsデータクラス (_MyCustomModuleParams) に置き換えます
            callback: AkariModuleType | None = None
        ) -> AkariDataSet | AkariData:
            self._logger.debug(f"_MyCustomModule 'stream_call' invoked with data: {data}, params: {params}")

            if not callback:
                raise ValueError("Callback must be provided for stream_call in _MyCustomModule")

            # --- ここにモジュールのストリーミングロジックを記述 ---
            if data.datasets and data.last().audio and data.last().audio.stream:
                audio_chunk = data.last().audio.stream.last()
                processed_info = f"Processed audio chunk of length {len(audio_chunk)}"

                intermediate_dataset = AkariDataSet()
                intermediate_dataset.text = AkariDataSetType(main=processed_info)

                data_for_callback = AkariData()
                data_for_callback.add(intermediate_dataset)

                # self._router.callModule の callback は公開名 (エイリアス) を使用することを想定
                # (例: MyCallbackModule)
                self._router.callModule(
                    moduleType=callback, # ここは登録された公開名
                    data=data_for_callback,
                    params=params,
                    streaming=True
                )

            final_dataset = AkariDataSet()
            final_dataset.text = AkariDataSetType(main="Stream processing ongoing or complete.")
            return final_dataset
    ```

    ストリーミング用に設計されたモジュールの例については、`modules.audio.mic._MicModule` や `modules.webrtcvad.vad._WebRTCVadModule` を参照してください。

5.  **(オプション) パラメータデータクラスの定義**
    ステップ 1 で既に `_MyCustomModuleParams` としてプライベート名で例を示しました。`AkariModuleParams` を継承することが推奨されます。このプライベートクラスも後述する `__init__.py` で公開します。

6.  **`AkariData` および `AkariDataSet` との対話**
    データの読み書きの方法は以前のガイドと同じですが、モジュール内で参照する際はプライベート名を使用します。

    **データの読み取り例:**

    ```python
    # _MyCustomModule のメソッド内
    if data.datasets and data.last().meta:
        meta_content = data.last().meta.main
        sample_rate = meta_content.get("rate")
        # ...
    ```

    **データの書き込み例 (音声メタデータ):**

    ```python
    # _MyCustomModule のメソッド内
    result_dataset.meta = AkariDataSetType(main={
        "rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "format": "wav",
    })
    ```

7.  **ロガーとルーターの使用**
    `self._logger` と `self._router` の使用方法は変わりません。

**例: `sample.module._SampleModule`**

提供されている `sample.module` も同様にプライベートクラスとして定義します。

```python
# modules/sample/_sample_module.py (ファイル名を変更し、クラス名をプライベートに)
from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)

class _SampleModule(AkariModule): # プライベート名に変更
    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        self._logger.debug("_SampleModule called") # クラス名を反映
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._logger.debug("Callback: %s", callback)
        return AkariDataSet()
```
