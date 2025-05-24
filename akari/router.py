import copy
import dataclasses
import time
from typing import Dict

import akari.data as akari_data
import akari.logger as logger
import akari.module as module


@dataclasses.dataclass
class _AkariRouterLoggerOptions:
    """AkariRouter のロギング設定を指定します。

    情報メッセージの冗長性とモジュール実行期間の追跡を制御します。

    Attributes:
        info (bool): ルーター操作中の一般的な情報メッセージのロギングを有効または無効にします。
            デフォルトは False です。
        duration (bool): 呼び出された各モジュールの実行時間のロギングを有効または無効にします。
            デフォルトは False です。
    """

    info: bool = False
    duration: bool = False


class _AkariRouter:
    """Akari モジュールの実行を調整します。

    利用可能なモジュールのレジストリを維持し、それらのタイプに基づいて呼び出しをディスパッチします。
    データフロー、パラメータ渡し、ストリーミングロジック、モジュールインタラクションのロギングを処理します。
    また、タイミングや使用されたパラメータなど、モジュール実行に関するメタデータも記録します。
    """

    def __init__(self, logger: logger._AkariLogger, options: _AkariRouterLoggerOptions | None = None) -> None:
        """AkariRouter インスタンスを構築します。

        Args:
            logger (_AkariLogger): すべてのルーターおよびモジュールのロギングアクティビティに使用される
                ロガーインスタンス。
            options (Optional[_AkariRouterLoggerOptions]): ルーターのロギング動作の特定の設定。
                None の場合、デフォルトのロギングオプションが適用されます。
        """
        if options is None:
            options = _AkariRouterLoggerOptions()
        self._modules: Dict[module._AkariModuleType, module._AkariModule] = {}
        self._logger = logger
        self._options = options

    def addModules(self, modules: Dict[module._AkariModuleType, module._AkariModule]) -> None:
        """1つ以上のモジュールをルーターに登録し、実行可能にします。

        各モジュールは、そのタイプをキーとして内部レジストリに追加されます。
        レジストリに既に存在するモジュールタイプを追加しようとすると、エラーが発生します。

        Args:
            modules (Dict[_AkariModuleType, _AkariModule]): キーがモジュールタイプ
                （`_AkariModule` を継承するクラス）で、値がそれらのモジュールのインスタンスである辞書。

        Raises:
            ValueError: `modules` 辞書に含まれるモジュールタイプが既にルーターに登録されている場合。
        """
        for moduleType, moduleInstance in modules.items():
            if moduleType not in self._modules:
                self._modules[moduleType] = moduleInstance
            else:
                raise ValueError(f"Module {moduleType} already exists in router.")

    def callModule(
        self,
        moduleType: module._AkariModuleType,
        data: akari_data._AkariData,
        params: module._AkariModuleParams,
        streaming: bool,
        callback: module._AkariModuleType | None = None,
    ) -> akari_data._AkariData:
        """指定された Akari モジュールを実行します。

        データフロー、パラメータ渡し、およびオプションのストリーミングコールバックを処理します。
        また、開始時刻や終了時刻など、モジュールの実行に関するメタデータを記録し、
        このメタデータを結果のデータセットに添付します。
        必要に応じてデータ分離を確保するために、入力 `data` のディープコピーが
        選択されたモジュールに渡される前に作成されます。

        Args:
            moduleType (module._AkariModuleType): 実行する Akari モジュールのクラスタイプ。
            data (akari_data._AkariData): モジュールの入力データオブジェクト。
            params (module._AkariModuleParams): モジュールに渡されるパラメータ。
            streaming (bool): モジュールをストリーミングモードで呼び出すかどうかを示すフラグ。
                True の場合、`selected_module.stream_call` が使用されます。
                それ以外の場合、`selected_module.call` が使用されます。
            callback (Optional[module._AkariModuleType]): 実行されたモジュールによって
                コールバックとして使用されるオプションのモジュールタイプ。特にストリーミング操作に関連します。

        Returns:
            akari_data._AkariData: 実行されたモジュールによって生成された新しいデータセットで
                変更または拡張された可能性のある `data` オブジェクト。

        Raises:
            ValueError: ルーターのモジュールレジストリが初期化されていない場合、
                要求された `moduleType` がレジストリに見つからない場合、または
                実行されたモジュールが予期しない型の結果を返す場合。
        """
        if self._modules is None:
            raise ValueError("Modules not set in router.")

        inputData = copy.deepcopy(data)

        selected_module = self._modules[moduleType]
        if selected_module is None:
            raise ValueError(f"Module {moduleType} not found in router.")

        if self._options.info:
            self._logger.info(
                "\n\n[Router] Module %s: %s",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
            )

        startTime = time.process_time()
        if streaming:
            result = selected_module.stream_call(inputData, params, callback)
        else:
            result = selected_module.call(inputData, params, callback)
        endTime = time.process_time()

        if isinstance(result, akari_data._AkariDataSet):
            result.setModule(
                akari_data._AkariDataModuleType(moduleType, params, streaming, callback, startTime, endTime)
            )
            data.add(result)
        elif isinstance(result, akari_data._AkariData):
            result.last().setModule(
                akari_data._AkariDataModuleType(moduleType, params, streaming, callback, startTime, endTime)
            )
            data = result
        else:
            raise ValueError(f"Invalid result type: {type(result)}")

        if self._options.duration:
            self._logger.info(
                "[Router] Module %s: %s took %.2f seconds",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
                endTime - startTime,
            )

        return data
