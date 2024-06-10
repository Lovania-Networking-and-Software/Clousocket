#
#  Copyright (C) 2024-present Lovania
#

import asyncio
import socket
import threading
import time

import hiredis

HOST = "127.0.0.1"
PORT = 4921


async def main():
    parser = hiredis.Reader()

    def send_data(data):
        for _ in range(10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as so:
                so.connect((HOST, PORT))
                so.sendall(data)
                parser.feed(so.recv(1024))
                time.sleep(0.1)

    for _ in range(100):
        threading.Thread(target=send_data, args=(hiredis.pack_command(("HEARTBEAT",)),)).start()


if __name__ == '__main__':
    asyncio.run(main())
