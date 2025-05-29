import dataclasses

from akari import (
    AkariData,
    AkariLogger,
    AkariModule,
    AkariModuleParams,
    AkariModuleType,
    AkariRouter,
)


@dataclasses.dataclass
class _SerialModuleParamModule:
    """Specifies a single Akari module's configuration for execution within a sequence managed by the SerialModule.

    Each instance of this class details which module to run, what parameters it
    should receive, and if any specific callback module should be associated with
    its execution within the sequence.

    Attributes:
        moduleType (AkariModuleType): The class type of the Akari module to be executed.
        moduleParams (AkariModuleParams): The specific parameters instance to be passed
            to the `call` or `stream_call` method of the `moduleType`.
        moduleCallback (Optional[AkariModuleType]): An optional Akari module type
            that will be passed as the callback to the executed module.
            Defaults to None, indicating no specific callback override for this step.
    """

    moduleType: AkariModuleType
    moduleParams: AkariModuleParams
    moduleCallback: AkariModuleType | None = None


@dataclasses.dataclass
class _SerialModuleParams:
    """Contains the ordered list of module configurations that the SerialModule will execute.

    The primary attribute `modules` holds a list, where each element is an
    instance of `_SerialModuleParamModule`, defining one step in the serial execution chain.

    Attributes:
        modules (list[_SerialModuleParamModule]): An ordered list of module execution
            definitions. The SerialModule will iterate through this list, executing
            each defined module in the specified order.
    """

    modules: list[_SerialModuleParamModule]


class _SerialModule(AkariModule):
    """Orchestrates the execution of a predefined list of Akari modules in a strict sequential order.

    This module takes a list of module configurations (type, parameters, and
    optional callback) and invokes each one using the AkariRouter. The output
    `AkariData` from one module becomes the input for the next, effectively
    chaining them together.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a SerialModule instance.

        Args:
            router (AkariRouter): The Akari router instance, necessary for calling
                each module in the defined sequence.
            logger (AkariLogger): The logger instance for recording operational details
                and debugging information.
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: _SerialModuleParams, callback: AkariModuleType | None = None) -> AkariData:
        """Processes an AkariData object by passing it sequentially through a configured list of Akari modules.

        For each module defined in `params.modules`, this method invokes the
        module using the AkariRouter. The `AkariData` object is updated with the
        result of each module call and then passed as input to the subsequent module.
        The `callback` argument passed to this `call` method is not used by the
        SerialModule itself during the execution of the sequence.

        Args:
            data (AkariData): The initial AkariData object to be processed by the
                first module in the sequence.
            params (_SerialModuleParams): An object containing the list of
                `_SerialModuleParamModule` instances, defining the modules to be
                executed and their respective parameters and callbacks.
            callback (Optional[AkariModuleType]): An optional callback module. This
                parameter is currently not utilized by the SerialModule in its
                orchestration logic.

        Returns:
            AkariData: The AkariData object after it has been processed by all
            modules in the configured sequence.
        """
        for module in params.modules:
            data = self._router.callModule(
                moduleType=module.moduleType,
                data=data,
                params=module.moduleParams,
                callback=module.moduleCallback,
                streaming=False,
            )

        return data

    def stream_call(
        self,
        data: AkariData,
        params: _SerialModuleParams,
        callback: AkariModuleType | None = None,
    ) -> AkariData:
        """Processes an AkariData object sequentially through configured modules, mirroring the non-streaming `call` behavior.

        Although named `stream_call`, this implementation currently iterates
        through the sequence of modules and calls each one in a non-streaming
        manner (i.e., `streaming=False` is passed to the router).
        True streaming behavior for the entire sequence is not implemented here;
        individual modules in the sequence might perform their own streaming
        if their `stream_call` is invoked by the router (which is not the case here).

        Args:
            data (AkariData): The initial AkariData object.
            params (_SerialModuleParams): The parameters defining the sequence of
                modules, identical to the `call` method.
            callback (Optional[AkariModuleType]): An optional callback module,
                passed along but not directly used by this method's sequential logic.

        Returns:
            AkariData: The AkariData object after processing by all modules in the sequence.
        """
        for module in params.modules:
            data = self._router.callModule(
                moduleType=module.moduleType,
                data=data,
                params=module.moduleParams,
                callback=module.moduleCallback,
                streaming=False,
            )

        return data
