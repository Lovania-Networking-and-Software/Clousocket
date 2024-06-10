#
#  Copyright (C) 2024-present Lovania
#

import math

import trio


class EndOfStream(Exception):
    pass


class IOQueue:
    def __init__(self, limit=math.inf):
        self.s_channel, self.r_channel = trio.open_memory_channel(limit)

    async def append(self, data, cid):
        await self.s_channel.send([data, cid])

    async def __aiter__(self):
        try:
            while True:
                try:
                    yield await self.recv_io_stream()
                except trio.EndOfChannel:
                    break
        except EndOfStream:
            raise EndOfStream()

    async def recv_io_stream(self):
        res = await self.r_channel.receive()
        return res
