#
#  Copyright (C) 2024-present Lovania
#

import typing

from src.middleware.serialisation import Command, Data, End, SubCommand


class Handler:
    def __init__(self, consul):
        self.consul = consul
        self.ops: typing.Dict[str, typing.Awaitable] = dict()

    def add_command(self, name: str, op: typing.Awaitable):
        self.ops[name] = op

    async def handle(self, proto, data: Command):
        raw_data = data
        if isinstance(data.next, SubCommand):
            op: typing.Awaitable = self.ops[f"{raw_data.this}_{raw_data.next.this}"]
            raw_data = raw_data.next
        else:
            op: typing.Awaitable = self.ops[raw_data.this]
        args = []
        if raw_data.next == End:
            pass
        else:
            while True:
                if raw_data.next == End():
                    break
                elif isinstance(raw_data.next, Data):
                    args.append(raw_data.next.this)
                    raw_data = raw_data.next
        await op(proto, *args)
