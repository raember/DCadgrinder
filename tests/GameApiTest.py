import unittest
import logging
from tests.WebClientMocker import *
from tests.testdata import *
from GameApi import GameApi


class GameApiTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.log = logging.getLogger(self.__class__.__name__)

    def test_identify_uuids(self):
        self.assertTrue(GameApi.is_uuid(UUIDs.KAMI))
        self.assertTrue(GameApi.is_uuid(UUIDs.POODIE))
        self.assertFalse(GameApi.is_uuid(Names.KAMI))
        self.assertFalse(GameApi.is_uuid(Names.POODIE))
        with self.assertRaises(Exception):
            GameApi.is_uuid(None)
            GameApi.is_uuid('')

    def test_get_name(self):
        fakewebclient = FakeWebClient(HARs.GAMEAPIS_PLAYER_NAME)
        api = GameApi(fakewebclient)
        self.assertEqual(Names.KAMI, api.get_name(UUIDs.KAMI))
        self.assertEqual(Names.POODIE, api.get_name(UUIDs.POODIE))
        with self.assertRaises(Exception):
            api.get_name(None)
            api.get_name('')

    def test_get_uuid(self):
        fakewebclient = FakeWebClient(HARs.GAMEAPIS_PLAYER_UUID)
        api = GameApi(fakewebclient)
        self.assertEqual(UUIDs.KAMI, api.get_uuid(Names.KAMI))
        self.assertEqual(UUIDs.POODIE, api.get_uuid(Names.POODIE))
