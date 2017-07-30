"""
This file declares the decorators which provides a simple API 
for subscribing to certain messages or perform periodic tasks through the same event loop.
"""

import asyncio, sys, types, socket, inspect
from contextlib import suppress
from typing import Dict, List, Tuple

import pyimc
from pyimc.udp import IMCProtocolUDP, get_imc_socket, get_multicast_socket


class IMCDecoratorBase:
    def add_event(self, loop, instance, fn):
        # Implements adding event to event loop
        # Ensure future was introduced in 3.4.4
        if sys.version_info < (3, 4, 4):
            recv_task0 = loop.create_task(fn)
        else:
            recv_task0 = asyncio.ensure_future(fn)

        return recv_task0


class Periodic(IMCDecoratorBase):
    """
    Calls the decorated function every N seconds
    """
    def __init__(self, time):
        self.time = time

    def __call__(self, fn, *args, **kwargs):
        try:
            fn._decorators.append(self)
        except AttributeError:
            fn._decorators = [self]
        return fn

    def add_event(self, loop, instance, fn):
        """
        Wraps the given function in a corutine which calls it every N seconds
        :param loop: The event loop (cls._loop)
        :param instance: The instantiated class
        :param fn: The function to be called
        :return: None
        """
        @asyncio.coroutine
        def periodic_fn():
            while True:
                fn()
                yield from asyncio.sleep(self.time)

        super().add_event(loop, instance, periodic_fn())


class Subscribe(IMCDecoratorBase):
    """
    Subscribes to the specified IMC Messages.
    Multiple types can be specified (e.g @Subscribe(pyimc.CpuUsage, pyimc.Heartbeat)
    """
    def __init__(self, *args, **kwargs):
        for arg in args:
            if arg.__module__ == 'imc':
                # Add to __imcsub__
                try:
                    self.subs.append(arg)
                except AttributeError:
                    self.subs = [arg]
            else:
                raise TypeError('Unknown message passed ({})'.format(arg))

    def __call__(self, fn, *args, **kwargs):
        try:
            fn._decorators.append(self)
        except AttributeError:
            fn._decorators = [self]
        return fn

    def add_event(self, loop, instance, fn):
        # Handled in IMCActor decorator to centralize the handling of messages
        pass


class IMCBase:
    def __init__(self):
        self._loop = None  # type: asyncio.BaseEventLoop
        self._task_mc = None  # type: asyncio.Task
        self._task_imc = None  # type: asyncio.Task
        self._subs = {}  # type: Dict[pyimc.Message, List[types.MethodType]]
        self._port_imc = None  # type: int
        self._port_mc = None  # type: int

    def add_subscription(self):
        # Add datagram endpoint for multicast announce
        multicast_listener = self._loop.create_datagram_endpoint(lambda: IMCProtocolUDP(self, is_multicast=True),
                                                                 family=socket.AF_INET)

        # Add datagram endpoint for UDP IMC messages
        imc_listener = self._loop.create_datagram_endpoint(lambda: IMCProtocolUDP(self, is_multicast=False),
                                                           family=socket.AF_INET)

        if sys.version_info < (3, 4, 4):
            self._task_mc = self._loop.create_task(multicast_listener)
            self._task_imc = self._loop.create_task(imc_listener)
        else:
            self._task_mc = asyncio.ensure_future(multicast_listener)
            self._task_imc = asyncio.ensure_future(imc_listener)

    def setup_event_loop(self):
        # Add event loop to instance
        if not self._loop:
            self._loop = asyncio.get_event_loop()

        # Collect decorated member functions, add them to event loop
        if type(self._subs) is not dict:
            self._subs = {}

        decorated = [(name, method) for name, method in inspect.getmembers(self) if hasattr(method, '_decorators')]
        for name, method in decorated:
            for decorator in method._decorators:
                decorator.add_event(self._loop, self, method)

                if type(decorator) is Subscribe:
                    # Collect types of messages for each function
                    for msg_type in decorator.subs:
                        try:
                            self._subs[msg_type].append(method)
                        except (KeyError, AttributeError):
                            self._subs[msg_type] = [method]
        if self._subs:
            self.add_subscription()

    def run(self):
        # Run setup if it hasn't been done yet
        if not self._loop:
            self.setup_event_loop()

        # Start event loop
        # TODO: set_exception_handler from @Exception(..) decorator
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            pending = asyncio.Task.all_tasks()
            for task in pending:
                task.cancel()
                # Now we should await task to execute it's cancellation.
                # Cancelled task raises asyncio.CancelledError that we can suppress when canceling
                with suppress(asyncio.CancelledError):
                    self._loop.run_until_complete(task)
        finally:
            self._loop.close()

if __name__ == '__main__':
    pass
