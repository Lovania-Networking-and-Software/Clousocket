#
#  Copyright (C) 2024-present Lovania
#
import trio

from src.consul import SupremeConsul
from src.gatehouse.abc_rule import ABCRule


class Rule(ABCRule):
    name = "Basic Test Rule"

    def __init__(self, consul: SupremeConsul):
        super().__init__(consul)

    async def handle(self, proto: trio.SocketStream, addr):
        return True


def export_rule(consul):
    return Rule(consul)
