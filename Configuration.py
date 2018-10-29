import logging
import os
import json
from enum import Enum
from datetime import datetime
from GameApi import GameApi


class Configuration:
    r"""Configuration class. Handles the management of all the configurations."""
    filename = "adgrinder.json"
    log = None
    json = {}
    interrupt_save = False

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    def __getitem__(self, item):
        return self.json[item]

    def get_proxy(self):
        r"""Select the first proxy that isn't flagged as abandoned.

        :return: Non abandoned proxy. None if there is no non abandoned proxy.
        :rtype: dict
        """
        for proxy in self.json[Keys.PROXIES]:
            if not proxy[Keys.ABANDONED]:
                return proxy
        return None

    def load(self):
        r"""Loads data from file.
        :return: self
        :rtype: Configuration
        """
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as config_file:
                jsonstr = config_file.read()
                if not jsonstr == '':
                    self.json = json.loads(jsonstr)
        return self

    def _default(self, key, value, node):
        r"""Checks if key exists in dict and sets it to a default value if not.

        :param key: The key to check for
        :type key: Keys
        :param value: The default value
        :type value: object
        :param node: The node to observe
        :type node: dict
        :return: True if the default has been set
        :rtype: bool
        """
        if key not in node:
            node[key] = value
            return True
        return False

    def complete_data(self, gameapi, name_or_uuid=''):
        r"""Completes datastructure.

        :param gameapi: GameApi to use when querying missing data(uuid/username).
        :type gameapi: GameApi
        :param name_or_uuid: Name or UUID to use if there is no player entry yet. Default: Asks user.
        :type name_or_uuid: str
        :return: self
        :rtype: Configuration
        """
        self._default(Keys.PLAYERS, [], self.json)
        if len(self.json[Keys.PLAYERS]) == 0:
            if name_or_uuid == '':
                name_or_uuid = input("Please enter player name or UUID: ")
            if GameApi.is_uuid(name_or_uuid):
                self.json[Keys.PLAYERS] = {"uuid": name_or_uuid}
            else:
                self.json[Keys.PLAYERS] = {"name": name_or_uuid}
        for player in self.json[Keys.PLAYERS]:
            if Keys.NAME in player and Keys.UUID not in player:
                uuid = gameapi.get_uuid(player[Keys.NAME])
                if uuid == "":
                    self.log.critical("Couldn't get UUID of user.")
                    self.interrupt_save = True
                    exit(1)
                player[Keys.UUID] = uuid
            elif Keys.NAME not in player and Keys.UUID in player:
                name = gameapi.get_name(player[Keys.UUID])
                if name == "":
                    self.log.warning("Assuming no name change.")
                    self.interrupt_save = True
                else:
                    player[Keys.NAME] = name
            self._default(Keys.LAST_LIMIT, datetime(1970, 1, 1, 0, 0, 0, 0).isoformat(), player)
            self._default(Keys.STATS, {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}, player)
        if not self._default(Keys.PROXIES, [], self.json):
            for proxy in self.json[Keys.PROXIES]:
                self._default(Keys.ADDRESS, '8.8.8.8', proxy)
                self._default(Keys.PORT, 80, proxy)
                self._default(Keys.STATS, {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}, proxy)
                self._default(Keys.ABANDONED, False, proxy)
        self._default(Keys.ABANDON_AFTER, 5, self.json)
        self._default(Keys.WATCH_DELAY, 180, self.json)
        self._default(Keys.LIMIT_DELAY, 1440, self.json)
        self._default(Keys.HEADLESS, True, self.json)
        self._default(Keys.INCOGNITO, False, self.json)
        self._default(Keys.START_DELAY, 5, self.json)
        return self

    def save(self):
        r"""Saves data to file.

        :return: self
        :rtype: Configuration
        """
        if self.interrupt_save:
            self.log.info("Skipped saving.")
            return
        with open(self.filename, 'w') as fp:
            json.dump(self.json, fp, indent=2)


class Keys(Enum):
    PLAYERS = "players"
    NAME = "name"
    UUID = "uuid"
    LAST_LIMIT = "last_limit"
    STATS = "stats"
    FULFILLED = "fulfilled"
    UNFILLED = "unfilled"
    LIMIT_REACHED = "limit_reached"
    PROXIES = "proxies"
    ADDRESS = "url"
    PORT = "port"
    USER = "user"
    PASSWORD = "password"
    ABANDONED = "abandoned"
    ABANDON_AFTER = "abandon_proxy_after"
    WATCH_DELAY = "ad_watch_delay"
    LIMIT_DELAY = "limit_delay"
    HEADLESS = "headless"
    START_DELAY = "start_delay"
    INCOGNITO = "incognito"
