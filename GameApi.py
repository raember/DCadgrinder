import logging
import re
import json
from Web import WebClient

class GameApi():
    r"""Mini wrapper for the web api of gameapis.net."""
    log = None
    webclient = None

    def __init__(self, webclient=WebClient()):
        r"""Creates new GameApi object.

        :param webclient: Web client to use
        :type webclient: WebClient
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.webclient = webclient

    @staticmethod
    def is_uuid(string):
        r"""Checks whether a string is a sane uuid.

        :param string: String to check
        :type string: str
        :return: Result of test
        :rtype: bool
        """
        if string is None or string == '':
            raise Exception("Non-empty string expected")
        match = re.compile('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$').match(string.lower())
        return match is not None

    def get_name(self, uuid):
        r"""Queries the name of a player identified by the given UUID.

        :param uuid: UUID of the player
        :type uuid: str
        :return: Name of the player
        :rtype: str
        """
        if not self.is_uuid(uuid):
            raise Exception("{} is not a valid UUID".format(uuid))
        self.log.info("Looking up name for {}".format(uuid))
        json_str = self.webclient.get("https://ss.gameapis.net/name/{}".format(uuid)).content.decode('utf-8')
        if not json_str.startswith("{"):
            self.log.warning("Couldn't get player name from server.")
            return ""
        return json.loads(json_str)['name']

    def get_uuid(self, name):
        r"""Queries the UUID of a player identified by the given name.

        :param name: Case insensitive name of the player
        :type name: str
        :return: UUID of the player
        :rtype: str
        """
        self.log.info("Looking up UUID for {}".format(name))
        json_str = self.webclient.get("https://use.gameapis.net/mc/player/uuid/{}".format(name)).content.decode('utf-8')
        id = json.loads(json_str)['id']
        return "{}-{}-{}-{}-{}".format(id[:8], id[8:12], id[12:16], id[16:20], id[20:32])