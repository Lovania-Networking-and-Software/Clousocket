#
#  Copyright (C) 2024-present Lovania
#
import abc

import trio


class ABCRule(abc.ABC):
    name: str

    def __init__(self, consul):
        self.consul = consul

    async def handle(self, proto: trio.SocketStream, addr) -> bool: ...
