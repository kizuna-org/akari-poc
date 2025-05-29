import json
from typing import Any

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    AkariRouter,
)


class _PrintModule(AkariModule):
    """Provides a debugging utility that logs the content of the most recent dataset in an AkariData sequence.

    Its primary function is to offer developers insight into the data structure
    and content at a specific point in the Akari pipeline. It logs various
    aspects of the last dataset, including a JSON representation if possible,
    and individual fields.
    """

    def __init__(self, router: AkariRouter, logger: AkariLogger) -> None:
        """Constructs a PrintModule instance.

        Args:
            router (AkariRouter): The Akari router instance, used for potential
                inter-module communication (though not directly used in this module's
                current implementation beyond the base class).
            logger (AkariLogger): The logger instance to which the dataset
                information will be written.
        """
        super().__init__(router, logger)

    def call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Inspects and logs the contents of the last AkariDataSet within the provided AkariData object.

        The method first attempts to serialize the entire last dataset to a JSON
        string for a comprehensive overview. If serialization fails (e.g., due to
        non-serializable data like bytes), it falls back to logging the raw string
        representation of the dataset.

        Subsequently, it iterates through all attributes of the last dataset. For
        attributes that are instances of `AkariDataSetType` and have a non-None
        `main` value, it logs the field name and this `main` value. For other
        non-None attributes, it logs their field name and value directly.

        Args:
            data (AkariData): The AkariData object containing the sequence of
                datasets. The last dataset in this sequence is the one inspected.
            params (Any): Parameters for this module. Currently, these parameters
                are logged but not otherwise used by the module's logic.
            callback (Optional[AkariModuleType]): An optional callback module.
                Currently, this parameter is logged but not used.

        Returns:
            AkariDataSet: The same last dataset that was inspected. This module
            does not modify the data.
        """
        self._logger.debug("PrintModule called")
        self._logger.debug("Data: %s", data)
        self._logger.debug("Params: %s", params)

        last = data.last()
        try:
            self._logger.info("Last Data: %s", json.dumps(last, indent=4))
        except:
            self._logger.info("Last Data: %s", last)

        for field in last.__dict__:
            if hasattr(last, field) and field != "module":
                value = getattr(last, field)
                if isinstance(value, AkariDataSetType):
                    if value.main is not None:
                        self._logger.info("%s: %s", field, value.main)
                else:
                    if value is not None:
                        self._logger.info("%s: %s", field, value)

        return data.last()

    def stream_call(self, data: AkariData, params: Any, callback: AkariModuleType | None = None) -> AkariDataSet:
        """Processes streaming data by applying the same logging logic as the non-streaming `call` method.

        This module treats streaming and non-streaming calls identically,
        logging the content of the last dataset received.

        Args:
            data (AkariData): The AkariData object, typically containing the latest
                chunk or segment of a stream as its last dataset.
            params (Any): Parameters for this module (logged but not used).
            callback (Optional[AkariModuleType]): An optional callback module
                (logged but not used).

        Returns:
            AkariDataSet: The last dataset from the input AkariData object.
        """
        return self.call(data, params, callback)
