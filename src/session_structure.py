#
#  Copyright (C) 2024-present Lovania
#

import time

import hiredis
import sentry_sdk
import trio


class HeatbeatTimeoutError(Exception):
    pass


class HeartbeatBase:
    def __init__(self, config):
        self.config: dict = config
        self.min_heartbeat = float(self.config["heartbeat"]["hb-min-interval"])
        self.max_heartbeat = float(self.config["heartbeat"]["hb-max-interval"])
        self.init_heartbeat_interval = float(self.config["heartbeat"]["hb-init-interval"])
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
    def __init__(self, proto: trio.SocketStream, consul, consular):
        self.last_activity_ts = None
        self.proto: trio.SocketStream = proto
        self.ht_base = HeartbeatBase(consul.config)
        self.heartbeat_timeout = int(consul.config["heartbeat"]["hb-timeout"])
        self.heartbeat_future = trio.Event()
        self.consul = consul
        self.consular = consular
        self.parser = hiredis.Reader()

    def between_callback(self):
        trio.from_thread.run(self.basis)

    async def basis(self):
        async with self.consular as cnslr:
            try:
                async with trio.open_nursery() as nursery:
                    cnslr.set_nursery(nursery)
                    nursery.start_soon(self.heartbeat)
                    nursery.start_soon(self.io)
            except* HeatbeatTimeoutError:
                await self.proto.send_all(hiredis.pack_command(("HEARTBEAT", "TIMEOUT")))
                nursery.cancel_scope.cancel()
            except* trio.BrokenResourceError:
                pass
            finally:
                await self.proto.aclose()

    async def heartbeat(self):
        while True:
            await trio.sleep(self.ht_base.heartbeat_interval_in_seconds)
            try:
                with trio.move_on_after(self.heartbeat_timeout / 1000) as scope:
                    await self.heartbeat_future.wait()
                    await self.ht_base.heartbeat()
                    await self.proto.send_all(
                        hiredis.pack_command(("HEARTBEAT", "ACK", f"{self.ht_base.heartbeat_interval}")))
                if scope.cancelled_caught:
                    raise TimeoutError()
            except TimeoutError:
                break
        raise HeatbeatTimeoutError("Heartbeat timed out")

    async def io(self):
        async for message in self.proto:
            with sentry_sdk.start_transaction(op="function", name="IO Middleware"):
                req = await self.consul.middleware.handle(message)
                if req.this == "not found":
                    await self.proto.send_all(hiredis.pack_command(("ERR", "unknown", "command", f"'{req.next.this}'")))
                    break
                if req.this == "heartbeat":
                    self.heartbeat_future.set()
                    continue
                self.ht_base.last_activity_ts = time.perf_counter()
                await self.handler(req)

    @sentry_sdk.trace
    async def handler(self, request):
        ts = time.perf_counter_ns()
        te = time.perf_counter_ns()
        self.last_activity_ts = time.perf_counter()
        sentry_sdk.metrics.distribution(key="data_handling", value=(te - ts) / 1000000, unit="millisecond")
