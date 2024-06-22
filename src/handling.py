#
#  Copyright (C) 2024-present Lovania
#
import trio

from src.middleware.serialisation import Command


class Handler:
    def __init__(self, consul, proto):
        self.consul = consul
        self.proto: trio.SocketStream = proto

    def handle(self, data: Command):
        pass
