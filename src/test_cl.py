#
#  Copyright (C) 2024-present Lovania
#

import asyncio
import socket
import threading

import hiredis

HOST = "127.0.0.1"
PORT = 4921


async def main():
    def send_data(data):
        for _ in range(1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as so:
                so.connect((HOST, PORT))
                so.sendall(data)
                so.recv(1024)

    for _ in range(128):
        threading.Thread(target=send_data, args=(hiredis.pack_command(("HEARTBEATt",)),)).start()


if __name__ == '__main__':
    asyncio.run(main())
