import asyncio
import json
import socket

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 4921  # The port used by the server


async def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(bytes(json.dumps({"op": 1}), "utf-8"))
        data = s.recv(1024)
        print(f"Received {data!r}")
        s.sendall(bytes(json.dumps({"op": 1}), "utf-8"))
        data = s.recv(1024)
        print(f"Received {data!r}")
        while True:
            await asyncio.sleep(0.5)
            s.sendall(bytes(json.dumps({"op": 0}), "utf-8"))
            data = s.recv(1024)
            print(data)
            s.sendall(bytes(json.dumps({"op": 1}), "utf-8"))
            data = s.recv(1024)
            print(data)


if __name__ == '__main__':
    asyncio.run(main())
