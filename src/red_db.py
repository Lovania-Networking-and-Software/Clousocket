import asyncio
import threading
import time
import uuid
from queue import Queue
from typing import AsyncIterator

import redis.asyncio as redis
import sentry_sdk


class EndOfStream(Exception):
    pass


class IOQueue:
    def __init__(self):
        self.queue = Queue()
        self.task_done = self.queue.task_done

    async def append(self, data, cid):
        self.queue.put([data, cid])

    async def __aiter__(self) -> AsyncIterator:
        try:
            while True:
                yield await self.recv_io_stream()
        except EndOfStream:
            raise EndOfStream()

    async def recv_io_stream(self):
        res = self.queue.get()
        return res


class RedisTPCS:
    def __init__(self, consul):
        self.consul = consul
        self.max_conns = int(self.consul.config["REDIS"]["MaxConnections"])
        self.threads = [threading.Thread(target=self.between_callback) for _ in range(self.max_conns - 1)]
        self.in_queue = IOQueue()
        self.out_queue = IOQueue()

    async def execute(self, command):
        with sentry_sdk.start_transaction(op="subprocess.communicate", name="Database Command Process"):
            pid = uuid.uuid1()
            await self.in_queue.append(command, pid)
            async for data, cid in self.out_queue:
                if cid == pid:
                    self.out_queue.task_done()
                    return data

    def start(self):
        [thrd.start() for thrd in self.threads]

    def between_callback(self):
        asyncio.run(self.starter())

    async def starter(self):
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.executor())

    async def executor(self):
        pool = redis.ConnectionPool(
            host=self.consul.config["REDIS"]["Endpoint"],
            port=self.consul.config["REDIS"]["Port"],
            password=self.consul.config["REDIS"]["Password"],
            max_connections=1,
            decode_responses=True,
            protocol=3
        )
        await pool.disconnect(True)
        async for comm, cid in self.in_queue:
            ts = time.perf_counter_ns()
            with sentry_sdk.start_transaction(op="db.redis", name="Database Command Exec.") as trs:
                try:
                    conn: redis.Redis = redis.Redis(connection_pool=pool)
                    res = await conn.execute_command(comm)
                    await self.out_queue.append(res, cid)
                    te = (time.perf_counter_ns() / 1000000) - ts / 1000000
                    sentry_sdk.set_measurement('redis_command_exec', te, 'miliseconds')
                    sentry_sdk.metrics.distribution(
                        key="database_command_exec_time",
                        value=te,
                        unit="millisecond"
                    )
                except Exception as err:
                    print(err)
                    sentry_sdk.capture_exception(err)
                    continue
                finally:
                    await conn.aclose()
                    await pool.disconnect(True)
                    self.in_queue.task_done()
                    trs.set_tag("command", comm.split(" ")[0])
