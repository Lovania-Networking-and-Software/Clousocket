import asyncio
import configparser
import json
import socket
import threading
import time

import sentry_sdk

from src.errors import DeadSignalError


class HeartbeatBase:
    def __init__(self, config):
        self.config: configparser.ConfigParser = config
        self.min_heartbeat = float(self.config["HEARTBEAT"]["HBMinInterval"])
        self.max_heartbeat = float(self.config["HEARTBEAT"]["HBMaxInterval"])
        self.init_heartbeat_interval = float(self.config["HEARTBEAT"]["HBInitInterval"])
        self.heartbeat_interval = self.init_heartbeat_interval
        self.heartbeat_interval_in_seconds = self.heartbeat_interval / 1000
        self.last_activity_ts = 0

    async def update_heartbeat(self):
        current_time = time.perf_counter()
        elapsed_time = current_time - self.last_activity_ts
        new_interval = max(self.min_heartbeat, self.init_heartbeat_interval + elapsed_time)
        new_interval = min(new_interval, self.max_heartbeat)
        self.heartbeat_interval = new_interval
        self.last_activity_ts = current_time

    async def heartbeat(self):
        if not self.last_activity_ts:
            self.last_activity_ts = time.perf_counter()
        await self.update_heartbeat()
        self.heartbeat_interval_in_seconds = self.heartbeat_interval / 1000


class Session:
    def __init__(self, proto: socket.socket, addr, consul, consular):
        self.last_activity_ts = None
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.thread: threading.Thread = threading.Thread(target=self.between_callback, daemon=True)
        self.proto = proto
        self.ht_base = HeartbeatBase(consul.config)
        self.heartbeat_timeout = int(consul.config["HEARTBEAT"]["HBTimeout"])
        self.heartbeat_future = self.loop.create_future()
        self.addr = addr
        self.consul = consul
        self.consular = consular

    async def start(self):
        self.thread.start()

    def between_callback(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.basis())

    async def basis(self):
        try:
            async with self.consular as cnslr:
                async with asyncio.TaskGroup() as tg:
                    cnslr.add_task(tg.create_task(self.heartbeat()))
                    cnslr.add_task(tg.create_task(self.io()))
                self.proto.close()
        except TimeoutError:
            self.proto.close()
        except DeadSignalError:
            return None

    async def heartbeat(self):
        while True:
            await asyncio.sleep(self.ht_base.heartbeat_interval_in_seconds)
            try:
                async with asyncio.timeout(self.heartbeat_timeout / 1000):
                    await self.heartbeat_future
                    await self.ht_base.heartbeat()
                    await self.loop.sock_sendto(self.proto,
                                                bytes(json.dumps({"op": -1,
                                                                  "d" : {"heartbeat_interval":
                                                                             self.ht_base.heartbeat_interval}
                                                                  }),
                                                      "utf-8"),
                                                self.addr)
                    self.heartbeat_future = self.loop.create_future()
            except TimeoutError:
                break
        raise TimeoutError("Heartbeat timed out")

    async def io(self):
        while True:
            message = await self.loop.sock_recv(self.proto, 1024)
            with (sentry_sdk.start_transaction(op="function", description="Process data (I/O)")):
                if message == b"":
                    break
                with sentry_sdk.start_span(op="serialize", description="Convert bytes to JSON") as spn:
                    ts = time.perf_counter_ns()
                    message = json.loads(message.decode('utf-8'))
                    te = time.perf_counter_ns()
                    spn.set_measurement("serialization", (te - ts) / 1000000, "miliseconds")
                if message["op"] == 0:
                    self.heartbeat_future.set_result(True)
                    continue
                self.ht_base.last_activity_ts = time.perf_counter()
                await self.handler(message)

    @sentry_sdk.trace
    async def handler(self, message):
        with sentry_sdk.start_span(op="function", description="Receive/Send Data"):
            ts = time.perf_counter_ns() / 1000000
            if message["op"] == 1:
                await self.loop.sock_sendto(self.proto, bytes(json.dumps({"op": 2,
                                                                          "d" :
                                                                              {"heartbeat_interval":
                                                                                   self.ht_base.heartbeat_interval}}),
                                                              "utf-8"),
                                            self.addr)
            te = time.perf_counter_ns() / 1000000
            self.last_activity_ts = time.perf_counter()
            sentry_sdk.metrics.distribution(
                key="data_handling",
                value=te - ts,
                unit="millisecond"
            )
