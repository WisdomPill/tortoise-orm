import inspect
from typing import List
from unittest.async_case import IsolatedAsyncioTestCase

from tortoise import Tortoise, current_transaction_map, generate_config
from tortoise.contrib.test import _restore_default

SimpleTestCase = IsolatedAsyncioTestCase


class IsolatedTestCase(IsolatedAsyncioTestCase):
    """
    An asyncio capable test class that will ensure that an isolated test db
    is available for each test.

    Use this if your test needs perfect isolation.

    Note to use ``{}`` as a string-replacement parameter, for your DB_URL.
    That will create a randomised database name.

    It will create and destroy a new DB instance for every test.
    This is obviously slow, but guarantees a fresh DB.

    If you define a ``tortoise_test_modules`` list, it overrides the DB setup module for the tests.
    """

    tortoise_test_modules: List[str] = []
    db_url: str = ''

    async def asyncSetUp(self) -> None:
        config = generate_config(self.db_url, app_modules={'models': self.tortoise_test_modules},
                                 testing=True, connection_label='models')
        await Tortoise.init(config, _create_db=True)
        await Tortoise.generate_schemas(safe=False)
        self._connections = Tortoise._connections.copy()

    async def asyncTearDown(self) -> None:
        Tortoise._connections = self._connections.copy()
        await Tortoise._drop_databases()


class TruncationTestCase(IsolatedTestCase):
    """
    An asyncio capable test class that will truncate the tables after a test.

    Use this when your tests contain transactions.

    This is slower than ``TestCase`` but faster than ``IsolatedTestCase``.
    Note that usage of this does not guarantee that auto-number-pks will be reset to 1.
    """

    # async def asyncSetUp(self) -> None:
    #     _restore_default()

    async def asyncTearDown(self) -> None:
        Tortoise._connections = self._connections.copy()
        # TODO: This is a naive implementation: Will fail to clear M2M and non-cascade foreign keys
        for app in Tortoise.apps.values():
            for model in app.values():
                await model.all().delete()


class TransactionTestContext:
    __slots__ = ("connection", "connection_name", "token")

    def __init__(self, connection) -> None:
        self.connection = connection
        self.connection_name = connection.connection_name

    async def __aenter__(self):
        current_transaction = current_transaction_map[self.connection_name]
        self.token = current_transaction.set(self.connection)
        if hasattr(self.connection, "_parent"):
            self.connection._connection = await self.connection._parent._pool.acquire()
        await self.connection.start()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.connection.rollback()
        if hasattr(self.connection, "_parent"):
            await self.connection._parent._pool.release(self.connection._connection)
        current_transaction_map[self.connection_name].reset(self.token)


class TestCase(IsolatedTestCase):
    """
    An asyncio capable test class that will ensure that each test will be run at
    separate transaction that will rollback on finish.

    This is a fast test runner. Don't use it if your test uses transactions.
    """

    # async def _asyncCallWithTransactionContext(self, func, /, *args, **kwargs):
    #     self.__db__ = Tortoise.get_connection("models")
    #     if self.__db__.capabilities.supports_transactions:
    #         connection = self.__db__._in_transaction().connection
    #         async with TransactionTestContext(connection):
    #             return await func(*args, **kwargs)
    #     else:
    #         return await func(*args, **kwargs)
    #
    # async def _callWithTransactionContext(self, func, /, *args, **kwargs):
    #     return await self._asyncCallWithTransactionContext(func, *args, **kwargs)
    #
    # def _callAsync(self, func, /, *args, **kwargs):
    #     assert self._asyncioTestLoop is not None
    #     assert inspect.iscoroutinefunction(func)
    #
    #     ret = self._callWithTransactionContext(func, *args, **kwargs)
    #     fut = self._asyncioTestLoop.create_future()
    #     self._asyncioCallsQueue.put_nowait((fut, ret))
    #     return self._asyncioTestLoop.run_until_complete(fut)
    #
    # def _callMaybeAsync(self, func, /, *args, **kwargs):
    #     assert self._asyncioTestLoop is not None
    #     if inspect.iscoroutinefunction(func):
    #         return self._callAsync(func, *args, **kwargs)
    #     else:
    #         return func(*args, **kwargs)

    def run(self, result=None):
        self._setupAsyncioLoop()
        try:
            # _restore_default()
            self.__db__ = Tortoise.get_connection("models")
            if self.__db__.capabilities.supports_transactions:
                connection = self.__db__._in_transaction().connection
                connection_name = connection.connection_name

                current_transaction = current_transaction_map[connection_name]
                token = current_transaction.set(connection)
                if hasattr(connection, "_parent"):
                    pool = connection._parent._pool
                    connection._connection = self._asyncioTestLoop.run_until_complete(pool.acquire())
                self._asyncioTestLoop.run_until_complete(connection.start())

                result = super().run(result)

                self._asyncioTestLoop.run_until_complete(connection.rollback())
                if hasattr(connection, "_parent"):
                    self._asyncioTestLoop.run_until_complete(connection._parent._pool.release(connection._connection))
                current_transaction_map[connection_name].reset(token)
            else:
                result = super().run(result)

            return result
        finally:
            self._tearDownAsyncioLoop()

    # async def asyncSetUp(self) -> None:
    #     pass
    #
    # async def asyncTearDown(self) -> None:
    #     if self.__db__.capabilities.supports_transactions:
    #         _restore_default()
    #     else:
    #         await super().asyncTearDown()
