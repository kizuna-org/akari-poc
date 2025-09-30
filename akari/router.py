import copy
import dataclasses
import os
import threading  # 追加
import time
from typing import Dict, cast

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
        # スレッドIDごとの最後のストリーム呼び出し完了時刻 (perf_counter) を格納
        self._thread_last_perf_counter: Dict[int, float] = {}

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

        selected_module = self._modules.get(moduleType)
        if selected_module is None:
            raise ValueError(f"Module {moduleType} not found in router.")

        current_thread_id = threading.get_ident()
        pid = os.getpid()

        if self._options.info:
            self._logger.info(
                "\n\n[Router] Module %s (PID: %s, ThreadID: %s): %s",
                "streaming" if streaming else "calling",
                pid,
                current_thread_id,
                selected_module.__class__.__name__,
            )

        # --- AkariDataModuleType に記録する startTime と endTime のための準備 ---
        # perf_counter を使用して実時間を計測
        current_perf_counter = time.perf_counter()

        # AkariDataModuleType に記録する startTime
        # これが「計測期間の開始点」となる
        startTime_for_dataset: float

        # このスレッドでの前回のストリーム呼び出しの終了時刻 (ストリーミングの場合のみ参照)
        last_stream_call_end_time_in_thread = self._thread_last_perf_counter.get(current_thread_id)

        if streaming:
            if last_stream_call_end_time_in_thread is None:  # このスレッドでの初回ストリーム呼び出し
                # 経過時間0の要件を満たすため、startTime はこの後の endTime と同じ値にする。
                # この時点では endTime は未定なので、モジュール実行後に endTime で startTime を上書きする。
                # 仮の startTime として、現在の時刻を設定しておく。
                startTime_for_dataset = current_perf_counter
            else:
                # 2回目以降のストリーム呼び出し: 前回の終了時刻を開始時刻とする
                startTime_for_dataset = last_stream_call_end_time_in_thread
        else:  # 非ストリーミング
            if data.datasets and data.last().module is not None:
                # 前のモジュールの終了時刻を開始時刻とする
                last_module = cast(akari_data._AkariDataModuleType, data.last().module)
                startTime_for_dataset = last_module.endTime
            else:
                # 前のモジュールがない場合は、現在の呼び出し処理開始時刻
                startTime_for_dataset = current_perf_counter

        # --- モジュールの実処理呼び出し ---
        # モジュールに渡す inputData の準備 (deepcopy)
        inputData = copy.deepcopy(data)

        if streaming:
            result = selected_module.stream_call(inputData, params, callback)
        else:
            result = selected_module.call(inputData, params, callback)

        # AkariDataModuleType に記録する endTime
        # モジュール実行完了後の時刻
        endTime_for_dataset: float = time.perf_counter()

        # ストリーミング初回呼び出しの場合、startTime を endTime と同じにして duration を0にする
        if streaming and last_stream_call_end_time_in_thread is None:
            startTime_for_dataset = endTime_for_dataset

        # ストリーミングの場合、このスレッドでの今回の呼び出しの終了時刻を保存
        if streaming:
            self._thread_last_perf_counter[current_thread_id] = endTime_for_dataset

        # --- 結果の処理と AkariDataModuleType の設定 ---
        if isinstance(result, akari_data._AkariDataSet):
            if result.module is None:
                result.setModule(
                    akari_data._AkariDataModuleType(
                        moduleType,
                        params,
                        streaming,
                        callback,
                        startTime_for_dataset,  # 修正後のstartTime
                        endTime_for_dataset,  # 修正後のendTime
                    )
                )
            data.add(result)
        elif isinstance(result, akari_data._AkariData):
            if result.datasets:  # result が空の AkariData を返す可能性も考慮
                result.last().setModule(
                    akari_data._AkariDataModuleType(
                        moduleType,
                        params,
                        streaming,
                        callback,
                        startTime_for_dataset,  # 修正後のstartTime
                        endTime_for_dataset,  # 修正後のendTime
                    )
                )
            data = result
        else:
            raise ValueError(f"Invalid result type: {type(result)}")

        if self._options.duration:
            # ここでログ出力する duration は、AkariDataModuleType に記録された endTime - startTime
            module = data.last().module
            duration = module.endTime - module.startTime if module else endTime_for_dataset - startTime_for_dataset
            self._logger.info(
                "[Router] Module %s: %s (ThreadID: %s) took %.4f seconds (elapsed since last relevant call)",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
                current_thread_id,
                duration,
            )

        return data
