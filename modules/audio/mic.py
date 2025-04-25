import dataclasses
from typing import Any
import time

import pyaudio
import threading

from akari import (
    AkariData,
    AkariDataSet,
    AkariDataSetType,
    AkariDataStreamType,
    AkariLogger,
    AkariModule,
    AkariModuleType,
    MainRouter,
)


@dataclasses.dataclass
class MicModuleParams:
    format: int = pyaudio.paInt16
    rate: int = 24000
    channels: int = 1
    frames_per_buffer: int = 1024
    input_device_index: int | None = None
    streamDurationMilliseconds: int = 5 * 100
    destructionMilliseconds: int = 5 * 100
    callbackParams: Any | None = None


class MicModule(AkariModule):
    def __init__(self, router: MainRouter, logger: AkariLogger) -> None:
        super().__init__(router, logger)

    def call(self, data: AkariData, params: MicModuleParams, callback: AkariModuleType | None = None) -> AkariDataSet:
        dataset = AkariDataSet()

        audio = pyaudio.PyAudio()

        streamer = audio.open(
            format=params.format,
            channels=params.channels,
            rate=params.rate,
            input=True,
            frames_per_buffer=params.frames_per_buffer,
            input_device_index=params.input_device_index,
        )

        self._logger.info("Recording started...")
        try:
            frames = []
            frame = b""
            frame_time = time.time()
            streamer.start_stream()

            abc = 0
            while True:
                data_chunk = streamer.read(params.frames_per_buffer, exception_on_overflow=False)
                frame += data_chunk

                current_time = time.time()
                if current_time - frame_time >= params.streamDurationMilliseconds / 1000:
                    frames.append(frame)

                    data = AkariData()
                    dataset = AkariDataSet()
                    stream = AkariDataStreamType(frames)
                    dataset.audio = AkariDataSetType(main=b"".join(frames), stream=stream)
                    data.add(dataset)
                    if callback is not None:

                        def call_module_in_thread() -> None:
                            nonlocal abc
                            print(abc)
                            abc += 1
                            self._router.callModule(
                                moduleType=callback,
                                data=data,
                                params=params.callbackParams,
                                streaming=True,
                            )

                        thread = threading.Thread(target=call_module_in_thread)
                        thread.start()

                    frame_time = current_time
                    frame = b""

                if len(frames) >= params.destructionMilliseconds / params.streamDurationMilliseconds:
                    frames = frames[1:]

        finally:
            streamer.stop_stream()
            streamer.close()
            audio.terminate()
