from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import akari.data as akari_data
import akari.logger as logger

if TYPE_CHECKING:
    import akari.router as router

_AkariModuleParams = Any
_AkariModuleType = type["_AkariModule"]


class _AkariModule(ABC):
    """Akari フレームワーク内のすべての処理ユニット（モジュール）の基本的な契約を定義します。

    任意のモジュールに期待される本質的な構造と動作を確立します。
    これには、モジュールがルーターやロガーなどのコアフレームワークコンポーネントで
    どのように初期化されるか、および標準のブロッキングコールとストリーミングコールの
    2つの主要な動作モードが含まれます。サブクラスは `call` を実装する必要があり、
    ストリーミング機能が必要な場合はオプションで `stream_call` をオーバーライドできます。

    Attributes:
        _router (router._AkariRouter): Akari ルーターへのアクセスを提供し、
            このモジュールが他のモジュールを呼び出し、パイプラインをナビゲートできるようにします。
        _logger (logger._AkariLogger): このモジュール専用のロガーインスタンスで、
            その操作と状態のコンテキスト化されたロギングを可能にします。
    """

    def __init__(self, router: router._AkariRouter, logger: logger._AkariLogger) -> None:
        """新しい Akari モジュールインスタンスを構築し、本質的なフレームワークコンポーネントを装備します。

        Args:
            router (router._AkariRouter): 中央の Akari ルーターインスタンスで、
                モジュール間の通信とパイプラインのオーケストレーションを容易にします。
            logger (logger._AkariLogger): このモジュール用に特別に設定されたロガーインスタンスで、
                イベントの記録とデバッグに使用されます。
        """
        self._router = router
        self._logger = logger

    @abstractmethod
    def call(
        self, data: akari_data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> akari_data._AkariDataSet | akari_data._AkariData:
        """ブロッキング、非ストリーミング方式で入力データに対してモジュールの主要なロジックを実行します。

        サブクラスは、コアデータ処理動作を定義するためにこのメソッドを実装する必要があります。
        このメソッドは、提供された `params` に従って入力 `data` を処理し、
        結果のデータセットを返す必要があります。

        Args:
            data (akari_data._AkariData): このモジュールの入力を含む AkariData インスタンスで、
                以前のモジュールからの結果を含む可能性があります。
            params (_AkariModuleParams): この `call` 実行の動作を設定する
                モジュール固有のパラメータ。
            callback (Optional[_AkariModuleType]): ロジックが必要とする場合にこのモジュールによって
                呼び出される可能性のあるオプションの Akari モジュールタイプ。
                通常、非ストリーミングコールの場合、さらに処理が必要な場合は、
                ルーターを介した直接呼び出しがより一般的です。

        Returns:
            Union[akari_data._AkariDataSet, akari_data._AkariData]: モジュールの処理の出力。
            モジュールが1つの個別の結果セットを生成する場合は単一の `_AkariDataSet` になり、
            モジュールが全体のデータパイプラインを変更したり複数のデータセットを生成したりする場合は
            `_AkariData` インスタンスになります。
        """
        pass

    def stream_call(
        self, data: akari_data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> akari_data._AkariDataSet | akari_data._AkariData:
        """連続的なデータフローや中間結果が必要な場合に適したストリーミング方式でモジュールのロジックを実行します。

        ストリーミング操作をサポートするモジュールは、このメソッドをオーバーライドする必要があります。
        デフォルトの実装は、ストリーミングがサポートされていないことを示します。
        ストリーミングは通常、チャンクまたはイベントでデータを処理し、
        中間結果で `callback` モジュールを呼び出す可能性があります。

        Args:
            data (akari_data._AkariData): AkariData インスタンス。初期データを提供したり、
                ストリームが結果を生成する場合に結果を蓄積するために使用されたりする場合があります。
            params (_AkariModuleParams): ストリーミング操作のモジュール固有のパラメータ。
            callback (Optional[_AkariModuleType]): ストリーミングプロセスからの中間結果または
                最終結果で呼び出される Akari モジュールタイプ。これは、
                ストリーミングデータを処理するための一般的なパターンです。

        Returns:
            Union[akari_data._AkariDataSet, akari_data._AkariData]: ストリーミング操作の
                最終結果または累積結果。正確な性質は、モジュールの実装によって異なります。

        Raises:
            NotImplementedError: 具体的なサブクラスがストリーミングコールをサポートしていない場合。
        """
        raise NotImplementedError("stream_call is not implemented in this module.")
