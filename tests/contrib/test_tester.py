# pylint: disable=W1503
from unittest import expectedFailure, skip

from tortoise.test_case import SimpleTestCase


class TestTesterSync(SimpleTestCase):
    def setUp(self):
        self.moo = "SET"

    def tearDown(self):
        self.assertEqual(self.moo, "SET")

    @skip("Skip it")
    def test_skip(self):
        self.assertTrue(False)

    @expectedFailure
    def test_fail(self):
        self.assertTrue(False)

    def test_moo(self):
        self.assertEqual(self.moo, "SET")


class TestTesterASync(SimpleTestCase):
    async def asyncSetUp(self):
        self.baa = "TES"

    async def asyncTearDown(self):
        self.assertEqual(self.baa, "TES")

    @skip("Skip it")
    async def test_skip(self):
        self.assertTrue(False)

    @expectedFailure
    async def test_fail(self):
        self.assertTrue(False)

    async def test_moo(self):
        self.assertEqual(self.baa, "TES")
