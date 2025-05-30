from __future__ import annotations

import copy
import dataclasses
import os
import threading  # 追加
import time
from typing import cast

import akari.data as akari_data
from akari import logger, module


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
        self._modules: dict[module._AkariModuleType, module._AkariModule] = {}  # UP006
        self._logger = logger
        self._options = options
        # スレッドIDごとの最後のストリーム呼び出し完了時刻 (perf_counter) を格納
        self._thread_last_perf_counter: dict[int, float] = {}  # UP006

    def add_modules(self, modules: dict[module._AkariModuleType, module._AkariModule]) -> None:  # N802, UP006
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
        for module_type, module_instance in modules.items():  # N806
            if module_type not in self._modules:
                self._modules[module_type] = module_instance
            else:
                # EM102: Exception must not use an f-string literal, assign to variable first
                # TRY003: Avoid specifying long messages outside the exception class
                msg = f"Module {module_type} already exists in router."
                raise ValueError(msg)

    def call_module(  # N802
        self,
        module_type: module._AkariModuleType,  # N803
        data: akari_data._AkariData,
        params: module._AkariModuleParams,
        streaming: bool,  # noqa: FBT001
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
            module_type (module._AkariModuleType): The class type of the Akari module to execute.

        Returns:
            akari_data._AkariData: The `data` object, potentially modified or augmented
            with new datasets produced by the executed module.

        Raises:
            ValueError: If the router's module registry has not been initialized,
                if the requested `module_type` is not found in the registry, or if
                the executed module returns a result of an unexpected type.
        """
        if self._modules is None:
            # EM101, TRY003
            msg = "Modules not set in router."
            raise ValueError(msg)

        selected_module = self._modules.get(module_type)
        if selected_module is None:
            # EM102, TRY003
            msg = f"Module {module_type} not found in router."
            raise ValueError(msg)

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
        start_time_for_dataset: float  # N806

        # このスレッドでの前回のストリーム呼び出しの終了時刻 (ストリーミングの場合のみ参照) # noqa: ERA001
        last_stream_call_end_time_in_thread = self._thread_last_perf_counter.get(current_thread_id)

        if streaming:
            if last_stream_call_end_time_in_thread is None:  # このスレッドでの初回ストリーム呼び出し
                # 経過時間0の要件を満たすため、startTime はこの後の endTime と同じ値にする。
                # この時点では endTime は未定なので、モジュール実行後に endTime で startTime を上書きする。
                # 仮の startTime として、現在の時刻を設定しておく。
                start_time_for_dataset = current_perf_counter  # N806
            else:
                # 2回目以降のストリーム呼び出し: 前回の終了時刻を開始時刻とする
                start_time_for_dataset = last_stream_call_end_time_in_thread  # N806
        elif data.datasets and data.last().module is not None:
            # 前のモジュールの終了時刻を開始時刻とする
            last_module = cast("akari_data._AkariDataModuleType", data.last().module)  # SLF001 - keep for now
            start_time_for_dataset = last_module.end_time  # N806 (from akari_data change)
        else:
            # 前のモジュールがない場合は、現在の呼び出し処理開始時刻
            start_time_for_dataset = current_perf_counter  # N806

        # --- モジュールの実処理呼び出し ---
        # モジュールに渡す inputData の準備 (deepcopy)
        input_data = copy.deepcopy(data)  # N806

        if streaming:
            result = selected_module.stream_call(input_data, params, callback)
        else:
            result = selected_module.call(input_data, params, callback)

        # AkariDataModuleType に記録する endTime
        # モジュール実行完了後の時刻
        end_time_for_dataset: float = time.perf_counter()  # N806

        # ストリーミング初回呼び出しの場合、startTime を endTime と同じにして duration を0にする
        if streaming and last_stream_call_end_time_in_thread is None:
            start_time_for_dataset = end_time_for_dataset  # N806

        # ストリーミングの場合、このスレッドでの今回の呼び出しの終了時刻を保存
        if streaming:
            self._thread_last_perf_counter[current_thread_id] = end_time_for_dataset # F821 fixed

        # --- 結果の処理と AkariDataModuleType の設定 ---
        if isinstance(result, akari_data._AkariDataSet):  # SLF001 - keep for now
            if result.module is None:
                result.set_module(  # N802 (from akari_data change)
                    akari_data._AkariDataModuleType(  # SLF001 - keep for now
                        module_type,
                        params,
                        streaming,
                        callback,
                        start_time_for_dataset,  # 修正後のstartTime
                        end_time_for_dataset,  # 修正後のendTime
                    ),
                )
            data.add(result)
        elif isinstance(result, akari_data._AkariData):  # SLF001 - keep for now
            if result.datasets:  # result が空の AkariData を返す可能性も考慮
                result.last().set_module(  # N802 (from akari_data change)
                    akari_data._AkariDataModuleType(  # SLF001 - keep for now
                        module_type,
                        params,
                        streaming,
                        callback,
                        start_time_for_dataset,  # 修正後のstartTime
                        end_time_for_dataset,  # 修正後のendTime
                    ),
                )
            data = result
        else:
            # EM102, TRY003, TRY004
            msg = f"Invalid result type: {type(result)}"
            raise ValueError(msg)

        if self._options.duration:
            # ここでログ出力する duration は、AkariDataModuleType に記録された endTime - startTime
            module_meta = data.last().module # Renamed to avoid conflict with 'module' import
            duration = module_meta.end_time - module_meta.start_time if module_meta else end_time_for_dataset - start_time_for_dataset # F821 fixed (on right side)
            self._logger.info(
                "[Router] Module %s: %s (ThreadID: %s) took %.4f seconds (elapsed since last relevant call)",
                "streaming" if streaming else "calling",
                selected_module.__class__.__name__,
                current_thread_id,
                duration,
            )

        return data
