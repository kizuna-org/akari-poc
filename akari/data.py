import dataclasses
from typing import Any, Dict, Generic, TypeVar

from akari.module import _AkariModuleParams, _AkariModuleType

T = TypeVar("T")


class _AkariDataStreamType(Generic[T]):
    """データポイントのシーケンスを管理します。通常、ストリーム内のデルタまたはチャンクを表します。

    型付けされたデータストリームを許可し、ストリーム内のすべての要素が
    一貫した型であることを保証します。最後の要素へのアクセス、長さの取得、
    インデックスによる要素の取得などの基本的な操作を提供します。

    Attributes:
        _delta (list[T]): データポイントのシーケンスを格納します。名前 `_delta` は
            これらのポイントが変更または増分を表す可能性があることを示唆していますが、
            任意のデータシーケンスを保持できます。
    """

    def __init__(self, delta: list[T]) -> None:
        """新しいデータストリームインスタンスを構築します。

        Args:
            delta (list[T]): ストリームに移入するデータポイントの初期リスト。
        """
        self._delta = delta

    def last(self) -> T:
        """ストリームに最後に追加されたデータポイントを取得します。

        Returns:
            T: 最後のデータポイント。

        Raises:
            IndexError: ストリームに要素が含まれていない場合。
        """
        if not self._delta:
            raise IndexError("No history available")
        return self._delta[-1]

    def __len__(self) -> int:
        """ストリーム内の現在のデータポイントの総数を計算します。

        Returns:
            int: データポイントの数。
        """
        return len(self._delta)

    def __getitem__(self, index: int) -> T:
        """ストリーム内の特定の位置（インデックス）にあるデータポイントにアクセスします。

        Args:
            index (int): 目的のデータポイントの0から始まるインデックス。

        Returns:
            T: 指定されたインデックスにあるデータポイント。

        Raises:
            IndexError: 指定されたインデックスがストリームの有効な範囲外の場合。
        """
        if index < 0 or index >= len(self._delta):
            raise IndexError("Index out of range")
        return self._delta[index]

    def __repr__(self) -> str:
        """データストリームの開発者向けの文字列表現を生成します。

        Returns:
            str: クラス名と内部デルタリストを示す文字列。
        """
        return f"AkariDataStreamType(delta={self._delta})"

    def __eq__(self, value: object) -> bool:
        """このデータストリームが別のオブジェクトと等価であるかどうかを判断します。

        等価性は、他のオブジェクトも `_AkariDataStreamType` であり、
        それらの内部 `_delta` リストが同一であるかどうかに基づいています。

        Args:
            value (object): このストリームと比較するオブジェクト。

        Returns:
            bool: オブジェクトが等価と見なされる場合は True、そうでない場合は False。
        """
        if not isinstance(value, _AkariDataStreamType):
            return NotImplemented
        return self._delta == value._delta


@dataclasses.dataclass
class _AkariDataModuleType:
    """特定のデータセットを生成した Akari モジュールの実行コンテキストを詳述するメタデータをカプセル化します。

    データの来歴を追跡し、パイプラインの動作を理解するための重要な情報を提供します。

    Attributes:
        moduleType: 実行された Akari モジュールの特定の型（クラス）。
        params: 実行中にモジュールに渡されたパラメータインスタンス。
        streaming (bool): モジュールがストリーミングコンテキストで呼び出されたかどうかを示します。
        callback (Optional[_AkariModuleType]): 実行されたモジュール用に構成されていた場合、
            コールバックモジュールの型。
        startTime (float): モジュールの実行開始を示すタイムスタンプ（`time.process_time()` から）。
        endTime (float): モジュールの実行完了を示すタイムスタンプ（`time.process_time()` から）。
    """

    moduleType: _AkariModuleType
    params: _AkariModuleParams
    streaming: bool
    callback: _AkariModuleType | None
    startTime: float
    endTime: float


class _AkariDataSetType(Generic[T]):
    """AkariDataSet 内の特定の型のデータ用の構造化されたコンテナを提供します。

    プライマリデータペイロード（`main`）、オプションの関連ストリーム（`stream`）、
    およびその他の関連データポイント（`others`）用の辞書を保持します。
    このジェネリッククラスは、これらのコンポーネントの型安全性を可能にします。

    Attributes:
        main (T): プライマリデータアーティファクト（例：テキスト文字列、オーディオバイトのブロック）。
        stream (Optional[_AkariDataStreamType[T]]): `main` に関連するオプションのデータストリーム。
            たとえば、`main` が完全な音声文字起こしである場合、`stream` には
            増分音声セグメントが含まれる場合があります。
        others (Dict[str, T]): `main` に文脈的に関連する同じ型 `T` の
            追加の名前付きデータポイントを格納するための辞書。
    """

    def __init__(
        self, main: T, stream: _AkariDataStreamType[T] | None = None, others: Dict[str, T] | None = None
    ) -> None:
        """新しい型指定されたデータセットを構築します。

        Args:
            main (T): このセットのプライマリデータポイント。
            stream (Optional[_AkariDataStreamType[T]]): 関連するデータポイントのオプションのストリーム。
                指定されていない場合は None にデフォルト設定されます。
            others (Optional[Dict[str, T]]): 同じ型 `T` の他の名前付きデータポイントの辞書。
                指定されていない場合は空の辞書にデフォルト設定されます。
        """
        self.main = main
        self.stream = stream
        self.others = others if others is not None else {}

    def __repr__(self) -> str:
        """型指定されたデータセットの開発者向けの文字列表現を生成します。

        Returns:
            str: クラス名とその `main`、`stream`、および `others` 属性を示す文字列。
        """
        return f"AkariDataSetType(main={self.main}, stream={self.stream}, others={self.others})"

    def __eq__(self, value: object) -> bool:
        """この型指定されたデータセットが別のオブジェクトと等価であるかどうかを判断します。

        等価性には、他のオブジェクトが `_AkariDataSetType` であり、
        それらの `main`、`stream`、および `others` 属性がそれぞれ等しいことが必要です。

        Args:
            value (object): この型指定されたデータセットと比較するオブジェクト。

        Returns:
            bool: オブジェクトが等価と見なされる場合は True、そうでない場合は False。
        """
        if not isinstance(value, _AkariDataSetType):
            return NotImplemented
        return self.main == value.main and self.stream == value.stream and self.others == value.others


class _AkariDataSet:
    """単一のモジュール実行によって生成されたさまざまな型のデータ（テキスト、オーディオ、ブール値、メタデータ）を集約します。

    また、モジュール実行自体のメタデータも格納します。このクラスは、
    Akari パイプラインのモジュール間で渡されるデータの標準化されたコンテナとして機能します。

    Attributes:
        module (_AkariDataModuleType): このデータセットを生成したモジュールに関するメタデータ。
            これは通常、モジュール実行後に AkariRouter によって設定されます。
        text (Optional[_AkariDataSetType[str]]): 文字列ベースのデータを保持します。
        audio (Optional[_AkariDataSetType[bytes]]): バイトベースのオーディオデータを保持します。
        bool (Optional[_AkariDataSetType[bool]]): ブール値を保持します。
        meta (Optional[_AkariDataSetType[dict[str, Any]]]): 辞書ベースのメタデータを保持します。
            オーディオサンプリングレートやコンテンツタイプなどの詳細によく使用されます。
        allData (Any | None): 事前定義されたカテゴリに適合しない他の型のデータ
            （生の API 応答など）を格納するための柔軟なフィールド。
    """

    module: _AkariDataModuleType

    def __init__(self) -> None:
        """空の AkariDataSet を構築し、モジュールによって移入される準備をします。"""
        self.text: _AkariDataSetType[str] | None = None
        self.audio: _AkariDataSetType[bytes] | None = None
        self.bool: _AkariDataSetType[bool] | None = None
        self.meta: _AkariDataSetType[dict[str, Any]] | None = None
        self.allData: Any | None = None

    def setModule(self, module: _AkariDataModuleType) -> None:
        """モジュール実行メタデータをこのデータセットに添付します。

        AkariRouter がデータセットを、それを作成したモジュールと
        それが実行されたパラメータに関連付けることを可能にします。この関連付けは、
        データの系統とデバッグに不可欠です。

        Args:
            module (_AkariDataModuleType): モジュールの実行コンテキストを記述する
                メタデータオブジェクト。
        """
        self.module = module


class _AkariData:
    """データセットのシーケンスを調整し、Akari処理パイプラインを介したデータの状態とフローを表します。

    パイプライン内のモジュールは通常、`_AkariData` インスタンスを受け取り、
    以前のデータセット（特に最後のデータセット）を検査し、結果を生成する際に
    新しい `_AkariDataSet` インスタンスをそれに追加できます。

    Attributes:
        datasets (list[_AkariDataSet]): データセットの順序付きリスト。新しいデータセットは
            このリストの末尾に追加されます。
    """

    def __init__(self) -> None:
        """最初に空のデータセットリストを持つ AkariData インスタンスを構築します。"""
        self.datasets: list[_AkariDataSet] = []

    def add(self, dataset: _AkariDataSet) -> None:
        """現在のシーケンスの末尾に新しいデータセットを追加します。

        Args:
            dataset (_AkariDataSet): 追加するデータセット。
        """
        self.datasets.append(dataset)

    def get(self, index: int) -> _AkariDataSet:
        """シーケンスからデータセットを0から始まるインデックスで取得します。

        Args:
            index (int): 取得するデータセットのインデックス。

        Returns:
            _AkariDataSet: 指定されたインデックスにあるデータセット。

        Raises:
            IndexError: インデックスがデータセットリストの有効な範囲外の場合。
        """
        if index < 0 or index >= len(self.datasets):
            raise IndexError("Index out of range")
        return self.datasets[index]

    def last(self) -> _AkariDataSet:
        """シーケンスに最後に追加されたデータセットにアクセスします。

        Returns:
            _AkariDataSet: リストの最後のデータセット。

        Raises:
            IndexError: データセットのリストが空の場合。
        """
        if not self.datasets:
            raise IndexError("No datasets available")
        return self.datasets[-1]

    def __getitem__(self, index: int) -> _AkariDataSet:
        """添字表記（例：`akari_data[i]`）を使用したデータセットの取得を有効にします。

        Args:
            index (int): 取得するデータセットのインデックス。

        Returns:
            _AkariDataSet: 指定されたインデックスのデータセット。
        """
        return self.get(index)

    def __len__(self) -> int:
        """シーケンス内の現在のデータセットの総数を計算します。

        Returns:
            int: データセットの数。
        """
        return len(self.datasets)
