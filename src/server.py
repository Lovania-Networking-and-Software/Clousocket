import asyncio
import socket

from src import consul


async def server():
    async with consul.SupremeConsul() as cn:
        print(f"Redis {await cn.db.execute('GET init')}ialized successfully.")

        loop = asyncio.get_running_loop()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((cn.host, cn.port))
            s.listen()
            async for _ in cn:
                conn, addr = await loop.sock_accept(s)
                await cn.create_session(conn, addr)


if __name__ == "__main__":
    try:
        with asyncio.Runner() as runner:
            runner.run(server())
    except KeyboardInterrupt:
        pass
