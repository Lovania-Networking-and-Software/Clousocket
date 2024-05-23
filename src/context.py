import socket


class Proto:
    def __init__(self, socket: socket.socket, consul):
        self.socket = socket
