#
#  Copyright (C) 2024-present Lovania
#

import functools
import json
import os
import time
import typing
from dataclasses import dataclass
from typing import Any

import hiredis
import sentry_sdk

from src.middleware.abc_mil import MIL


class CommandNotFound(Exception):
    pass


class ArgumentError(Exception):
    pass


@dataclass
class End:
    pass


@dataclass
class Data:
    this: typing.Any
    next: typing.Union[End, typing.Any]


@dataclass
class SubCommand:
    this: str
    next: typing.Union[Data, End]


@dataclass
class Command:
    this: str
    next: typing.Union[SubCommand, Data, End]


class Serialiser:
    def __init__(self):
        self.commands = {}
        self.args = {}
        self._update()

    def _update(self):
        directory_path = "./commands"
        for filename in os.listdir(directory_path):
            filepath = os.path.join(directory_path, filename)
            if os.path.isfile(filepath):
                self._load_command_from_file(filename, filepath)

    def _load_command_from_file(self, filename, filepath):
        cmd_info = {}
        cmd = filename.split(".")[0]
        cmd_info[cmd] = {"args": None}
        splitted = cmd.split("-")
        cmd_name = splitted[0]
        sub_cmd_name = splitted[1] if len(splitted) == 2 else None

        with open(filepath, "r") as f:
            cmd_info.update(json.load(f))

        self._register_command(
            cmd_name, sub_cmd_name, cmd_info[cmd]["function"], cmd_info[cmd]["args"]
        )

    def _register_command(self, cmd_name, sub_cmd_name, function, args):
        if sub_cmd_name:
            self._register_sub_command(cmd_name, sub_cmd_name, function, args)
        else:
            self._register_main_command(cmd_name, function, args)

    def _register_main_command(self, cmd_name, function, args):
        self.commands.setdefault(cmd_name, {0: None, 1: {}})
        self.commands[cmd_name][0] = function

        if args:
            self.args.setdefault(cmd_name, {0: None, 1: {}})
            self.args[cmd_name][0] = {arg["name"]: arg for arg in args}

    def _register_sub_command(self, cmd_name, sub_cmd_name, function, args):
        self.commands.setdefault(cmd_name, {0: None, 1: {}})
        self.commands[cmd_name][1][sub_cmd_name] = function

        if args:
            self.args.setdefault(cmd_name, {0: None, 1: {}})
            self.args[cmd_name][1][sub_cmd_name] = {arg["name"]: arg for arg in args}

    @sentry_sdk.trace
    @functools.lru_cache()
    def convert_request(
        self, *request: str, recursive: bool = False
    ) -> typing.Union[Command, SubCommand, Data, End]:
        ts = time.perf_counter_ns()
        if len(request) == 0:
            sentry_sdk.set_measurement(
                "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
            )
            return End()
        elif not recursive:
            cmd = request[0].lower()
            if cmd not in self.commands.keys():
                raise CommandNotFound(f"Command '{cmd}' not found.")

            if len(request) == 1:
                sentry_sdk.set_measurement(
                    "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
                )
                return Command(this=cmd, next=End())

            if len(request) == 2:
                sub_cmd = request[1]
                if sub_cmd in self.commands[cmd][1]:
                    sentry_sdk.set_measurement(
                        "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
                    )
                    return Command(this=cmd, next=SubCommand(this=sub_cmd, next=End()))
                else:
                    sentry_sdk.set_measurement(
                        "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
                    )
                    return Command(this=cmd, next=Data(this=sub_cmd, next=End()))

            data = request[1:]
            sub_cmd = request[1]
            if sub_cmd in self.commands[cmd][1]:
                sentry_sdk.set_measurement(
                    "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
                )
                return Command(
                    this=cmd,
                    next=SubCommand(
                        sub_cmd, next=self.convert_request(*data[1:], recursive=True)
                    )
                )
            sentry_sdk.set_measurement(
                "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
            )
            return Command(
                this=cmd,
                next=Data(
                    this=data[0], next=self.convert_request(*data[1:], recursive=True)
                ),
            )
        else:
            data = request[1:]
            sentry_sdk.set_measurement(
                "serialisation", (time.perf_counter_ns() - ts) / 1000000, "miliseconds"
            )
            return Data(
                this=request[0], next=self.convert_request(*data, recursive=True)
            )


class ReaderMIL(MIL):
    def __init__(self):
        self.r = hiredis.Reader(encoding="utf-8")

    @sentry_sdk.trace
    @functools.lru_cache()
    def handle(self, request) -> list[str]:
        self.r.feed(request)
        return self.r.gets()


class SerialiserMIL(MIL):
    def __init__(self):
        self.s = Serialiser()

    @sentry_sdk.trace
    def handle(self, request) -> Any:
        return self.s.convert_request(*request)
