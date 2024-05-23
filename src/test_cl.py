import asyncio
import json
import socket

import hiredis

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 4921  # The port used by the server

async def main():
    parser = hiredis.Reader()

    async def send_data(data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(data)
            return await asyncio.get_running_loop().sock_recv(s, 1024)

    async with asyncio.TaskGroup() as tg:
        for _ in range(1):
            await asyncio.sleep(0.5)
            print(hiredis.pack_command(("HEARTBEAT",)))
            tg.create_task(send_data(hiredis.pack_command(("HEARTBEAT",))))
            data = await send_data(hiredis.pack_command(("HEARTBEAT",)))
            parser.feed(data)
            print(parser.gets())

if __name__ == '__main__':
    asyncio.run(main())