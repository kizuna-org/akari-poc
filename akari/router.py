import copy
import dataclasses
import os
import threading  # 追加
import time
from typing import Dict

import akari.data as akari_data
import akari.logger as logger
import akari.module as module


@dataclasses.dataclass
class _AkariRouterLoggerOptions:
    """Specifies logging preferences for the AkariRouter.

    Controls the verbosity of informational messages and the tracking of
    module execution durations.

    Attributes:
        info (bool): Enables or disables logging of general informational messages
            during router operations. Defaults to False.
        duration (bool): Enables or disables logging of the execution time for
            each called module. Defaults to False.
    """

    info: bool = False
    duration: bool = False


class _AkariRouter:
    """Orchestrates the execution of Akari modules.

    Maintains a registry of available modules and dispatches calls to them
    based on their type. It handles data flow, parameter passing, streaming
    logic, and logging of module interactions. It also records metadata about
    module execution, such as timing and parameters used.
    """

    def __init__(self, logger: logger._AkariLogger, options: _AkariRouterLoggerOptions | None = None) -> None:
        """Constructs an AkariRouter instance.

        Args:
            logger (_AkariLogger): The logger instance to be used for all router
                and module logging activities.
            options (Optional[_AkariRouterLoggerOptions]): Specific configuration
                for the router's logging behavior. If None, default logging
                options are applied.
        """
        if options is None:
            options = _AkariRouterLoggerOptions()
        self._modules: Dict[module._AkariModuleType, module._AkariModule] = {}
        self._logger = logger
        self._options = options
        # スレッドIDごとの最後のストリーム呼び出し完了時刻 (perf_counter) を格納
        self._thread_last_perf_counter: Dict[int, float] = {}

    def addModules(self, modules: Dict[module._AkariModuleType, module._AkariModule]) -> None:
        """Registers one or more modules with the router, making them available for execution.

        Each module is added to an internal registry, keyed by its type.
        Attempting to add a module type that already exists in the registry
        will result in an error.

        Args:
            modules (Dict[_AkariModuleType, _AkariModule]): A dictionary where keys
                are module types (classes inheriting from `_AkariModule`) and values
                are instances of those modules.

        Raises:
            ValueError: If a module type included in the `modules` dictionary
                has already been registered with the router.
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
        """Executes a specified Akari module.

        Handles data flow, parameter passing, and optional streaming callbacks.
        It also records metadata about the module's execution, such as start
        and end times, and attaches this metadata to the resulting dataset.
        A deep copy of the input `data` is made before passing it to the
        selected module to ensure data isolation if needed.

        Args:
            moduleType (module._AkariModuleType): The class type of the Akari module to execute.
            data (akari_data._AkariData): The input data object for the module.
            params (module._AkariModuleParams): The parameters to be passed to the module.
            streaming (bool): A flag indicating whether the module should be called
                in streaming mode. If True, `selected_module.stream_call` is used;
                otherwise, `selected_module.call` is used.
            callback (Optional[module._AkariModuleType]): An optional module type to be
                used as a callback by the executed module, particularly relevant
                for streaming operations.

        Returns:
            akari_data._AkariData: The `data` object, potentially modified or augmented
            with new datasets produced by the executed module.

        Raises:
            ValueError: If the router's module registry has not been initialized,
                if the requested `moduleType` is not found in the registry, or if
                the executed module returns a result of an unexpected type.
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
            if data.datasets and hasattr(data.last(), "module"):
                # 前のモジュールの終了時刻を開始時刻とする
                startTime_for_dataset = data.last().module.endTime
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
            duration = endTime_for_dataset - startTime_for_dataset
            self._logger.info(
                "[Router] Module %s: %s (ThreadID: %s) took %.4f seconds (elapsed since last relevant call)",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
                current_thread_id,
                duration,
            )

        return data
