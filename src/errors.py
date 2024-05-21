class Execution(Exception):
    def __init__(self, reason=None):
        self.reason = reason

    def __str__(self):
        return f"Server executed.{f' Reason {self.reason}' if self.reason else ''}"


class DeadSignalError(Exception):
    def __str__(self):
        return "Dead signal received."
