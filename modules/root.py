"""Root module for the Akari pipeline."""

from __future__ import annotations

from akari_core.module import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _RootModule(AkariModule):
    """Initiates the Akari pipeline by invoking the first module."""

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a RootModule instance.

        Args:
            router (AkariRouter): The Akari router instance, essential for
                calling the first module in the pipeline.
            logger (AkariLogger): The logger instance for recording module
                activity and debugging information.
        """
        super().__init__(router, logger)

    def call(
        self,
        data: AkariData,
        params: AkariModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Initiate the Akari pipeline by invoking the first module."""
        self._logger.debug("RootModule called")

        # The RootModule's responsibility is typically to just kick off the pipeline
        # by calling the first configured module. The actual processing happens
        # downstream.

        # In a simple sequential pipeline, this might look like:
        # result_data = self._router.callModule(params.first_module_type, data, params.first_module_params, callback=callback)
        # return result_data.last() if result_data.datasets else AkariDataSet()

        # For now, just return the input data as is, assuming downstream modules will process it.
        # This is a placeholder; actual logic depends on pipeline structure.
        self._logger.info("RootModule is a placeholder and does not perform processing.")
        self._logger.info("Input Data: %s", data)
        self._logger.info("Params: %s", params)
        self._logger.info("Callback: %s", callback)

        # Assuming the next module is handled by the router based on configuration
        # or the next step is implicit. Returning input data or an empty dataset.
        return data.last() if data.datasets else AkariDataSet()

    def stream_call(
        self,
        data: AkariData,
        params: AkariModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariDataSet:
        """Initiate the Akari streaming pipeline by invoking the first module."""
        self._logger.debug("RootModule stream_call called")

        # Similar to call, this is a placeholder for initiating streaming.
        self._logger.info("RootModule stream_call is a placeholder.")

        # Assuming the next streaming module is handled by the router.
        return data.last() if data.datasets else AkariDataSet()
