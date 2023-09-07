"""
Flaskaesque helper functions for aiohttp.
"""
import asyncio
import functools
import types
import typing
from concurrent.futures import ThreadPoolExecutor


def asyncify(
    func: typing.Callable[..., typing.Any],
) -> typing.Callable[..., typing.Awaitable[typing.Any]]:
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if hasattr(self, "executor") is False:
            self.executor = ThreadPoolExecutor(max_workers=5)
        bound = functools.partial(func, self, *args, **kwargs)
        if asyncio.get_event_loop().is_running():
            loop = asyncio.get_event_loop()
            return loop.run_in_executor(self.executor, bound)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_in_executor(self.executor, bound)

    return typing.cast(typing.Callable[..., typing.Awaitable[typing.Any]], wrapper)


def aio(max_workers: int = 5) -> typing.Callable[[typing.Type], typing.Type]:
    """Decorator that converts all the methods of a class into async methods."""

    def decorator(cls: typing.Type) -> typing.Type:
        attrs: typing.Dict[str, typing.Any] = {}
        attrs["executor"] = ThreadPoolExecutor(max_workers=max_workers)
        for attr_name, attr_value in cls.__dict__.items():
            if (
                isinstance(attr_value, types.FunctionType)
                and attr_name.startswith("__") is False
            ):
                attrs[attr_name] = asyncify(attr_value)
            else:
                attrs[attr_name] = attr_value
        return type(cls.__name__, cls.__bases__, attrs)

    return decorator
