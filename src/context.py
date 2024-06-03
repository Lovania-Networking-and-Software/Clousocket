#
#  Copyright (C) 2024-present Lovania
#

import socket


class Proto:
    def __init__(self, socket: socket.socket, consul):
        self.socket = socket
