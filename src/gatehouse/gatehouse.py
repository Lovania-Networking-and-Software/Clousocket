#
#  Copyright (C) 2024-present Lovania
#

import glob
import importlib
import importlib.util
import sys
import time
import uuid

import sentry_sdk
import trio

from src.gatehouse.abc_rule import ABCRule
from src.utils import IOQueue


def _load_from_module_spec(spec: importlib.machinery.ModuleSpec, key: str):
    lib = importlib.util.module_from_spec(spec)
    sys.modules[key] = lib
    try:
        spec.loader.exec_module(lib)
    except Exception as e:
        del sys.modules[key]
        raise Exception(key, e) from e
    try:
        getattr(lib, 'export_rule')
    except AttributeError:
        del sys.modules[key]
        raise Exception("No Entry Point Erro: " + key)
    return lib


def load_names(name: str):
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise Exception(f"Module not found: {name}")
    return _load_from_module_spec(spec, name)


class Gatehouse:
    def __init__(self, consul):
        self.consul = consul
        self.thread_count = consul.config["gatehouse"]["thread-count"]
        self.in_queue = IOQueue()
        self.out_queue = IOQueue()
        self.rules: list[ABCRule] = []
        names = glob.glob('./gatehouse/rules/*')
        for nn in names:
            if nn.endswith("__pycache__"):
                continue
            name = nn[18:]
            name = name[0:len(name) - 3]
            rule_m = load_names(f"gatehouse.rules.{name}")
            rule = getattr(rule_m, "export_rule")(self.consul)
            self.rules.append(rule)

    async def execute(self, proto: trio.SocketStream, addr):
        with sentry_sdk.start_transaction(op="subprocess.communicate", name="Gatehouse Handling"):
            pid = uuid.uuid1()
            await self.in_queue.append((proto, addr), pid)
            async for data, cid in self.out_queue:
                if cid == pid:
                    return data

    async def starter(self):
        for _ in range(self.thread_count):
            trio.lowlevel.spawn_system_task(self.gate)

    async def gate(self):
        async for comm, cid in self.in_queue:
            proto: trio.SocketStream = comm[0]
            addr = comm[1]
            ts = time.perf_counter_ns()
            checks = dict()
            with sentry_sdk.start_transaction(op="middleware.handle", name="Gatehouse Gate Check"):
                try:
                    for rule in self.rules:
                        rule_res = await rule.handle(proto, addr)
                        if not rule_res:
                            res = False
                            break
                        res = True
                        checks[rule.name] = res
                    await self.out_queue.append(res, cid)
                    te = (time.perf_counter_ns() - ts) / 1000000
                    sentry_sdk.set_measurement('redis_command_exec', te, 'miliseconds')
                    sentry_sdk.metrics.distribution(
                        key="gatehouse_handling_duration",
                        value=te,
                        unit="millisecond"
                    )
                    sentry_sdk.set_context("Gate Rules Responses", checks)
                except Exception as err:
                    sentry_sdk.capture_exception(err)
                    continue
