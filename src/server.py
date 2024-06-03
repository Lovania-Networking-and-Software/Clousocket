#
#  Copyright (C) 2024-present Lovania
#

import sentry_sdk
import trio

from src import consul


async def server():
    async with consul.SupremeConsul() as cn:
        print(f"Redis {await cn.db.execute('GET', 'init')}ialized successfully.")

        try:
            async with trio.open_nursery() as nursery:
                await nursery.start(trio.serve_tcp, cn.create_session, cn.port)
        except* KeyboardInterrupt:
            raise KeyboardInterrupt()
        except* Exception as err:
            sentry_sdk.capture_exception(err)


if __name__ == "__main__":
    try:
        trio.run(server)
    except* KeyboardInterrupt:
        print("Closed")
