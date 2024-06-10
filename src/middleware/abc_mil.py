#
#  Copyright (C) 2024-present Lovania
#

import abc
from typing import Any


class MIL(abc.ABC):
    async def handle(self, request) -> Any: ...
