import asyncio
import configparser
import socket
import uuid

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.socket import SocketIntegration

from src import red_db, session_structure
from src.errors import Execution


class SupremeConsul:
    def __init__(self):
        self.config: configparser.ConfigParser
        self.sessions: dict[str, session_structure.Session] = dict[str, session_structure.Session]()
        self.consulars: list[Consular] = list[Consular]()
        self.nid = uuid.uuid1()
        self.dead_signal = asyncio.Event()
        self.loop = asyncio.get_event_loop()
        self.db: red_db.RedisTPCS
        self.redis_psc = None
        self.ids: dict[id, id] = dict[id, id]()
        self.dead_channel = "channel:dead_signal"

    async def __aenter__(self):
        self.config = configparser.ConfigParser()
        self.config.read('clousocket.conf')

        self.host = self.config["NETWORK"]["HOST"]
        self.port = int(self.config["NETWORK"]["PORT"])

        sentry_sdk.init(
            dsn=self.config["SENTRY"]["DSN"],
            traces_sample_rate=float(self.config["SENTRY"]["TracesSampleRate"]),
            profiles_sample_rate=float(self.config["SENTRY"]["ProfilesSampleRate"]),
            enable_tracing=True,
            integrations=[
                AsyncioIntegration(),
                SocketIntegration(),
            ]
        )

        self.db = red_db.RedisTPCS(self)
        self.db.start()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        sentry_sdk.get_client().close()

    async def __aiter__(self):
        while True:
            try:
                yield await self.io()
            except Execution as e:
                sentry_sdk.capture_exception(e)
                raise e

    async def io(self):
        return self

    async def create_session(self, sck: socket.socket, addr):
        with sentry_sdk.start_transaction(op="task", name="Session starting"):
            cnslr = Consular(self)
            ses = session_structure.Session(sck, addr, self, cnslr)
            sesid = id(ses)
            self.sessions[str(uuid.uuid3(self.nid, f"{sesid}"))] = ses
            self.ids[id(cnslr)] = sesid
            await ses.start()


class Consular:
    def __init__(self, consul: SupremeConsul):
        self.consul = consul
        self.tasks: list[asyncio.Task] = list[asyncio.Task]()

    def add_task(self, task):
        self.tasks.append(task)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del self.consul.sessions[str(uuid.uuid3(self.consul.nid, f"{self.consul.ids[id(self)]}"))]
        return None
