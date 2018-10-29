import logging
import os
import json
from datetime import datetime
from GameApi import GameApi


class Configuration:
    r"""Configuration class. Handles the management of all the configurations."""
    filename = "adgrinder.json"
    log = None
    json = None
    PLAYERS = "players"
    NAME = "name"
    UUID = "uuid"
    LAST_LIMIT = "last_limit"
    STATS = "stats"
    FULFILLED = "fulfilled"
    UNFILLED = "unfilled"
    LIMIT_REACHED = "limit_reached"
    PROXIES = "proxies"
    URL = "url"
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
    interrupt_save = False

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    def __getitem__(self, item):
        return self.json[item]

    def create_example_config(self):
        r"""Creates an example config file which hasn't been updated.

        :return: self
        :rtype: Configuration
        """
        if os.path.exists(self.filename):
            os.remove(self.filename)
        self.load().complete_data()
        self.json[self.PLAYERS] = []
        self.json[self.PLAYERS].append({self.NAME: 'Harambe'})
        self.json[self.PLAYERS].append({self.UUID: '069a79f4-44e9-4726-a5be-fca90e38aaf5'})
        self.json[self.PROXIES].append({self.URL: "8.8.8.8"})
        return self

    def get_proxy(self):
        r"""Select the first proxy that isn't flagged as abandoned.

        :return: Unabandoned proxy. None if there is no unabandoned proxy.
        :rtype: dict
        """
        for proxy in self.json[self.PROXIES]:
            if not proxy[self.ABANDONED]:
                return proxy
        return None

    def load(self):
        r"""Loads data from file.
        :return: self
        :rtype: Configuration
        """
        if not os.path.exists(self.filename):
            self.json = {}
        else:
            with open(self.filename, 'r') as config_file:
                config = config_file.read()
                if config == '':
                    self.json = {}
                else:
                    self.json = json.loads(config)
        return self

    def complete_data(self, webclient=None):
        r"""Completes datastructure.

        :param webclient: Web client to use when querying missing data(uuid/username). If not provided, players don't
        get updated.
        :type webclient: WebClient
        :return: self
        :rtype: Configuration
        """
        if webclient is not None:
            gapi = GameApi(webclient)
            if self.PLAYERS not in self.json:
                var = input("Please enter player name or UUID: ")
                if GameApi.is_uuid(var):
                    self.json = {"players": [{"uuid": var}]}
                else:
                    self.json = {"players": [{"name": var}]}
            for player in self.json[self.PLAYERS]:
                if self.NAME in player and self.UUID not in player:
                    uuid = gapi.get_uuid(player[self.NAME])
                    if uuid == "":
                        self.log.critical("Couldn't get UUID of user.")
                        self.interrupt_save = True
                        exit(1)
                    player[self.UUID] = uuid
                elif self.NAME not in player and self.UUID in player:
                    name = gapi.get_name(player[self.UUID])
                    if name == "":
                        self.log.warning("Assuming no name change.")
                        self.interrupt_save = True
                    else:
                        player[self.NAME] = name
                if self.LAST_LIMIT not in player:
                    player[self.LAST_LIMIT] = datetime(1970, 1, 1, 0, 0, 0, 0).isoformat()
                if self.STATS not in player:
                    player[self.STATS] = {self.FULFILLED: 0, self.UNFILLED: 0, self.LIMIT_REACHED: 0}
        if self.PROXIES not in self.json:
            self.json[self.PROXIES] = []
        else:
            for proxy in self.json[self.PROXIES]:
                if self.PORT not in proxy:
                    proxy[self.PORT] = 80
                if self.USER not in proxy:
                    proxy[self.USER] = ""
                if self.PASSWORD not in proxy:
                    proxy[self.PASSWORD] = ""
                if self.STATS not in proxy:
                    proxy[self.STATS] = {self.FULFILLED: 0, self.UNFILLED: 0, self.LIMIT_REACHED: 0}
                if self.ABANDONED not in proxy:
                    proxy[self.ABANDONED] = False
        if self.ABANDON_AFTER not in self.json:
            self.json[self.ABANDON_AFTER] = 5
        if self.WATCH_DELAY not in self.json:
            self.json[self.WATCH_DELAY] = 180
        if self.LIMIT_DELAY not in self.json:
            self.json[self.LIMIT_DELAY] = 1440
        if self.HEADLESS not in self.json:
            self.json[self.HEADLESS] = True
        if self.INCOGNITO not in self.json:
            self.json[self.INCOGNITO] = True
        if self.START_DELAY not in self.json:
            self.json[self.START_DELAY] = 5
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