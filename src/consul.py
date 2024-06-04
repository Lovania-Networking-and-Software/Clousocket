#
#  Copyright (C) 2024-present Lovania
#

import tomllib
import typing
import uuid

import sentry_sdk
import trio
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.socket import SocketIntegration

from src import red_db, session_structure
from src.errors import Execution
import apex


class SupremeConsul:

    def __init__(self):
        self.config: dict
        self.sessions: dict[str, session_structure.Session] = dict[str, session_structure.Session]()
        self.consulars: list[Consular] = list[Consular]()
        self.nid = uuid.uuid1()
        self.db: red_db.RedisTPCS
        self.ids: dict[id, id] = dict[id, id]()
        self.nursery: typing.Union[trio.Nursery, None] = None

    async def __aenter__(self):
        async with trio.open_nursery() as self.nursery:
            with open("../clousocket.toml", "rb") as f:
                self.config = tomllib.load(f)
            self.limiter = trio.CapacityLimiter(int(self.config["threading"]["thread-limit"]))

            self.host = self.config["network"]["host"]
            self.port = int(self.config["network"]["port"])

            sentry_sdk.init(
                dsn=self.config["sentry"]["dsn"],
                traces_sample_rate=float(self.config["sentry"]["traces-sample-rate"]),
                profiles_sample_rate=float(self.config["sentry"]["profiles-sample-rate"]),
                enable_tracing=True,
                integrations=[
                    AsyncioIntegration(),
                    SocketIntegration(),
                ]
            )

            self.db = red_db.RedisTPCS(self)
            self.nursery.start_soon(self.db.starter)
            self.wt = WatchTower(self)

            trio.lowlevel.spawn_system_task(self.wt.watchman)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        sentry_sdk.get_client().close()
        await self.db.out_queue.s_channel.aclose()
        await self.db.out_queue.r_channel.aclose()
        await self.db.in_queue.s_channel.aclose()
        await self.db.in_queue.r_channel.aclose()

    async def __aiter__(self):
        while True:
            try:
                yield await self.io()
            except Execution as e:
                sentry_sdk.capture_exception(e)
                raise e

    async def io(self):
        return self

    async def create_session(self, sck: trio.SocketStream):
        with sentry_sdk.start_transaction(op="task", name="Session starting"):
            cnslr = Consular(self)
            ses = session_structure.Session(sck, self, cnslr)
            sesid = id(ses)
            self.sessions[str(uuid.uuid3(self.nid, f"{sesid}"))] = ses
            self.ids[id(cnslr)] = sesid
            await trio.to_thread.run_sync(ses.between_callback, limiter=self.limiter)


class WatchTower:
    def __init__(self, consul: SupremeConsul):
        self.consul = consul

    async def watchman(self):
        while True:
            await trio.sleep(2)
            sentry_sdk.metrics.gauge(
                key="trio_tasks_living",
                value=trio.lowlevel.current_statistics().tasks_living
            )


class Consular:
    def __init__(self, consul: SupremeConsul):
        self.consul = consul
        self.nursery: typing.Union[trio.Nursery, None] = None

    def set_nursery(self, nursery: trio.Nursery):
        self.nursery = nursery

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del self.consul.sessions[str(uuid.uuid3(self.consul.nid, f"{self.consul.ids[id(self)]}"))]
        return None
