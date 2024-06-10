#
#  Copyright (C) 2024-present Lovania
#

import time

import sentry_sdk

from src.middleware.abc_mil import MIL


class Middleware:
    def __init__(self, *mils: MIL):
        self.mils = mils

    @sentry_sdk.trace
    async def handle(self, request):
        ts = time.perf_counter_ns()
        for mil in self.mils:
            request = mil.handle(request)
        sentry_sdk.set_measurement(
            "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
        )
        return request
