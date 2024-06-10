#
#  Copyright (C) 2024-present Lovania
#

import time
import uuid

import redio
import sentry_sdk
import trio

from src.utils import IOQueue


class RedisTPCS:
    def __init__(self, consul):
        self.consul = consul
        self.max_conns = int(self.consul.config["redis"]["max-connections"])
        self.in_queue = IOQueue()
        self.out_queue = IOQueue()
        self.pool = redio.Redis(self.consul.config["redis"]["url"], pool_max=self.max_conns)

    async def execute(self, *inp):
        with sentry_sdk.start_transaction(op="subprocess.communicate", name="Database Command Process"):
            pid = uuid.uuid1()
            await self.in_queue.append(inp, pid)
            async for data, cid in self.out_queue:
                if cid == pid:
                    return data

    async def starter(self):
        for _ in range(self.max_conns):
            trio.lowlevel.spawn_system_task(self.executor)

    async def executor(self):
        async for comm, cid in self.in_queue:
            ts = time.perf_counter_ns()
            with sentry_sdk.start_transaction(op="db.redis", name="Database Command Exec.") as trs:
                conn = self.pool()
                try:
                    res = await conn._command(*comm).autodecode
                    await self.out_queue.append(res, cid)
                    te = (time.perf_counter_ns() / 1000000) - ts / 1000000
                    sentry_sdk.set_measurement('redis_command_exec', te, 'miliseconds')
                    sentry_sdk.metrics.distribution(
                        key="database_command_exec_time",
                        value=te,
                        unit="millisecond"
                    )
                except Exception as err:
                    sentry_sdk.capture_exception(err)
                    continue
                finally:
                    del conn
                    trs.set_tag("command", comm[0])
