"""
This file declares the decorators which provides a simple API 
for subscribing to certain messages or perform periodic tasks through the same event loop.
"""

import asyncio
import sys
import types
import socket
import inspect
import logging
from contextlib import suppress
from typing import Dict, List, Tuple, Type, Union

from pyimc.udp import IMCProtocolUDP


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
    def __init__(self, time: Union[int, float]):
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
        # Verify function signature
        argspec = inspect.getfullargspec(fn)
        n_args = len(argspec.args) - 1 if 'self' in argspec.args else len(argspec.args)
        n_required_args = n_args - (len(argspec.defaults) if argspec.defaults else 0)
        assert n_required_args == 0, 'Functions decorated with @Periodic cannot have any required parameters.'

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
            if arg.__module__ == '_pyimc':
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

        # Verify function signature
        argspec = inspect.getfullargspec(fn)
        n_args = len(argspec.args) - 1 if 'self' in argspec.args else len(argspec.args)
        assert n_args >= 1, 'Functions decorated with @Subscribe must have a parameter for the message.'

        n_required_args = n_args - (len(argspec.defaults) if argspec.defaults else 0)
        assert n_required_args <= 1, 'Functions decorated with @Subscribe can only have one required parameter.'

        # Add typing information if not already defined
        first_arg = argspec.args[1] if 'self' in argspec.args else argspec.args[0]
        if first_arg not in argspec.annotations.keys():
            fn.__annotations__[first_arg] = self.subs[-1]

        return fn

    def add_event(self, loop, instance, fn):
        # Handled in IMCBase decorator to centralize the handling of messages
        pass


if __name__ == '__main__':
    pass
