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
    """Defines the foundational contract for all processing units (modules) within the Akari framework.

    Establishes the essential structure and behavior expected of any module.
    This includes how modules are initialized with core framework components like
    the router and logger, and the two primary modes of operation: a standard
    blocking call and a streaming call. Subclasses must implement `call` and
    can optionally override `stream_call` if streaming capabilities are required.

    Attributes:
        _router (router._AkariRouter): Provides access to the Akari router, enabling
            this module to call other modules and navigate the pipeline.
        _logger (logger._AkariLogger): A dedicated logger instance for this module,
            allowing for contextualized logging of its operations and state.
    """

    def __init__(self, router: router._AkariRouter, logger: logger._AkariLogger) -> None:
        """Constructs a new Akari module instance, equipping it with essential framework components.

        Args:
            router (router._AkariRouter): The central Akari router instance, facilitating
                inter-module communication and pipeline orchestration.
            logger (logger._AkariLogger): The logger instance specifically configured
                for this module, used for recording events and debugging.
        """
        self._router = router
        self._logger = logger

    @abstractmethod
    def call(
        self, data: akari_data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> akari_data._AkariDataSet | akari_data._AkariData:
        """Executes the module's primary logic on the input data in a blocking, non-streaming fashion.

        Subclasses must implement this method to define their core data processing
        behavior. The method should process the input `data` according to the
        provided `params` and return the resulting dataset(s).

        Args:
            data (akari_data._AkariData): The AkariData instance containing the input
                for this module, potentially including results from previous modules.
            params (_AkariModuleParams): Module-specific parameters that configure
                the behavior of this `call` execution.
            callback (Optional[_AkariModuleType]): An optional Akari module type
                that could be invoked by this module if its logic requires it.
                Typically, for non-streaming calls, direct invocation via the
                router is more common if further processing is needed.

        Returns:
            Union[akari_data._AkariDataSet, akari_data._AkariData]: The output of
            the module's processing. This can be a single `_AkariDataSet` if the
            module produces one distinct set of results, or an `_AkariData` instance
            if the module modifies the overall data pipeline or produces multiple datasets.
        """
        pass

    def stream_call(
        self, data: akari_data._AkariData, params: _AkariModuleParams, callback: _AkariModuleType | None = None
    ) -> akari_data._AkariDataSet | akari_data._AkariData:
        """Executes the module's logic in a streaming fashion, suitable for continuous data flows or when intermediate results are needed.

        Modules that support streaming operations should override this method.
        The default implementation indicates that streaming is not supported.
        Streaming typically involves processing data in chunks or events and
        potentially invoking a `callback` module with intermediate results.

        Args:
            data (akari_data._AkariData): The AkariData instance, which may provide
                initial data or be used to accumulate results if the stream produces them.
            params (_AkariModuleParams): Module-specific parameters for the streaming operation.
            callback (Optional[_AkariModuleType]): An Akari module type to be invoked
                with intermediate or final results from the streaming process. This is
                a common pattern for handling streamed data.

        Returns:
            Union[akari_data._AkariDataSet, akari_data._AkariData]: The final or
            cumulative result of the streaming operation. The exact nature depends
            on the module's implementation.

        Raises:
            NotImplementedError: If the concrete subclass does not support streaming calls.
        """
        raise NotImplementedError("stream_call is not implemented in this module.")
