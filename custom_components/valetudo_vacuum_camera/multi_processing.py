"""
Multiprocessing module (version 1.6.0)
This module provide the image multiprocessing in order to
avoid the overload of the main_thread of Home Assistant.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from multiprocessing import Event, Process, Queue
import os
import threading

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameraProcessor:
    def __init__(self):
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.stop_event = Event()
        self.worker_processes = []

    async def _process_task(self, target, args, kw):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, target, *args, **kw)

    async def _worker_process(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            current_tid = threading.current_thread().name
            current_pid = os.getpid()
            while not self.stop_event.is_set():
                task = self.task_queue.get()
                if task is None:
                    _LOGGER.info(f"Worker process {current_pid} completed.")
                    break  # Stop processing when None is received

                target, args, kw = task
                result = await self._process_task(target, args, kw)
                self.result_queue.put(result)
                _LOGGER.debug(
                    f"Process {current_pid}, Thread {current_tid} completed a task."
                )

    async def process_image(self, target, args, kw):
        self.task_queue.put((target, args, kw))
        _LOGGER.debug(f"Task cue updated with target: {target}")

    async def start_processing(self, num_processes=3):
        # Starting the one process per CPU core.
        for _ in range(num_processes):
            process = Process(target=self._worker_process)
            self.worker_processes.append(process)
            process.start()
            _LOGGER.debug(f"New process started with PID: {process.pid}")
        # Joining the process threads.
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, process.join)
            for process in self.worker_processes
        ]
        _LOGGER.debug(f"{tasks} on process.")
        await asyncio.gather(*tasks)

    async def stop_processing(self):
        # Signal worker processes to stop
        for _ in range(len(self.worker_processes)):
            self.task_queue.put(None)
        # Wait for worker processes to finish
        for process in self.worker_processes:
            await process.join()
            _LOGGER.debug(f"Process: {process.pid}, have now None in queue.")
            # if process.is_alive():
            #     process.terminate()
