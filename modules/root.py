from akari import (
    AkariData,
    AkariDataSet,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


class _RootModule(AkariModule):
    """Serves as the entry point or starting trigger for an Akari data processing pipeline.

    Its primary responsibility is to kick off a sequence of module executions.
    It does this by taking a module type as a parameter and using the AkariRouter
    to invoke that initial module. It typically does not perform any data
    processing itself but rather delegates to other modules.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a RootModule instance.

        Args:
            router (AkariRouter): The Akari router instance, essential for
                calling the first module in the pipeline.
            logger (AkariLogger): The logger instance for recording module
                activity and debugging information.
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: AkariModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Initiates the Akari pipeline by invoking the first processing module.

        The `params` argument for this RootModule's `call` method is uniquely
        interpreted as the type (class) of the Akari module that should be
        executed first. The router is then instructed to call this target module,
        passing along the initial `data` and any `callback`. The RootModule
        itself returns an empty `AkariDataSet`, as its role is purely
        orchestration.

        Args:
            data (AkariData): The initial AkariData instance for the pipeline,
                which is typically empty when starting a new sequence.
            params (AkariModuleParams): Expected to be the AkariModuleType (class)
                of the first module to be executed in the pipeline. This will be
                used as the `moduleType` argument for `router.callModule`.
            callback (Optional[AkariModuleType]): An optional callback module type
                that will be passed to the first module's execution.

        Returns:
            AkariDataSet: An empty `AkariDataSet`. The actual results of the
            pipeline are expected to be accumulated within the `AkariData` object
            passed through subsequent module calls.
        """
        self._logger.debug("RootModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)
        self._router.callModule(moduleType=params, data=data, params=None, streaming=False, callback=callback)

        return AkariDataSet()
