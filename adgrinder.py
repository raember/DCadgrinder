#!/usr/bin/env python3

import argparse
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta

import requests
from dateutil import parser
from requests import Response
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)16s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
from selenium import webdriver


# from selenium.webdriver.common.proxy import Proxy, ProxyType
# from selenium.webdriver.common.keys import Keys


class Main:
    r"""Main program. Manages ad watchers in parallel."""
    log = None
    args = None
    conf = None

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        parser = argparse.ArgumentParser(description="Watches Ads")
        parser.add_argument('-r', '--reset', action='store_true',
                            help="Reset statistics and exit.")
        parser.add_argument('-c', '--create-config', action='store_true',
                            help="Create sample config and exit.")
        parser.add_argument('-u', '--update', action='store_true',
                            help="Update player names and exit.")
        parser.add_argument('-d', '--delete-abandoned', action='store_true',
                            help="Delete abandoned proxy servers and exit.")
        parser.add_argument('-t', '--test', action='store_true',
                            help="Test proxy server and exit.")
        parser.add_argument('-a', '--abandon-proxy', action='store_true',
                            help="Abandon current proxy server and exit.")
        self.args = parser.parse_args()

    def run(self):
        # Handle arguments:
        if self.args.create_config:
            self.log.info('Creating sample config file.')
            Config().create_example_config().save()
            exit(0)
        if self.args.abandon_proxy:
            self.log.info('Marking current proxy as abandoned.')
            conf = Config().load()
            proxy = conf.get_proxy()
            if proxy is None:
                self.log.info("No more proxies to abandon.")
            else:
                self.log.info("Abandoning {}.".format(proxy[Config.URL]))
                proxy[Config.ABANDONED] = True
                conf.save()
            exit(0)
        if self.args.delete_abandoned:
            self.log.info('Deleting abandoned proxies.')
            conf = Config().load()
            for proxy in conf[Config.PROXIES]:
                if proxy[Config.ABANDONED]:
                    self.log.info("Deleting proxy {}.".format(proxy[Config.URL]))
                    conf[Config.PROXIES].remove(proxy)
            conf.save()
            exit(0)
        webclient = WebClient(os.getenv('HTTP_PROXY'))
        if self.args.update:
            self.log.info('Updating player names from UUIDs.')
            conf = Config().load()
            for player in conf[Config.PLAYERS]:
                if Config.NAME in player:
                    del (player[Config.NAME])
            conf.complete_data(webclient)
            conf.save()
            exit(0)
        if self.args.test:
            self.log.info('Running proxy test.')
            conf = Config().load().complete_data(webclient)
            watcher = AdWatcher(conf[Config.PLAYERS][0], conf)
            watcher.setup()
            while not watcher.does_proxy_work():
                watcher.quit()
                watcher.setup()
            watcher.quit()
            conf.save()
            exit(0)
        if self.args.reset:
            self.log.info('Resetting statistics.')
            conf = Config().load().complete_data(webclient)
            for player in conf[Config.PLAYERS]:
                player[Config.STATS] = {Config.FULFILLED: 0, Config.UNFILLED: 0, Config.LIMIT_REACHED: 0}
            for proxy in conf[Config.PROXIES]:
                proxy[Config.STATS] = {Config.FULFILLED: 0, Config.UNFILLED: 0, Config.LIMIT_REACHED: 0}
            conf.save()
            exit(0)

        # Let's go!
        conf = Config().load().complete_data(webclient)
        conf.save()  # So we have a sexy formatted config file.
        self.log.info("Watching ads for the following players: {}".format(
            ", ".join([p[Config.NAME] for p in conf[Config.PLAYERS]])))
        watcherthreads = []
        for player in conf[Config.PLAYERS]:
            watcher = AdWatcher(player, conf)
            if watcher.is_limit_expired():
                watcher.setup()
                thread = threading.Thread(target=watcher.watch_all)
                thread.start()
                watcherthreads.append(thread)
                self.log.info("Started ad watcher thread. Waiting {}s.".format(conf[Config.START_DELAY]))
                time.sleep(conf[Config.START_DELAY])
        try:
            for thread in watcherthreads:
                thread.join()
        except KeyboardInterrupt:
            conf.save()
        self.log.info("Finished.")


class Config:
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
        :rtype: Config
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
        :rtype: Config
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
        :rtype: Config
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
        :rtype: Config
        """
        if self.interrupt_save:
            self.log.info("Skipped saving.")
            return
        with open(self.filename, 'w') as fp:
            json.dump(self.json, fp, indent=2)


class AdWatcher():
    r"""Handles the watching of ads for a specific player."""
    log = None
    player = None
    config = None
    proxy = None
    browser = None

    def __init__(self, player, config):
        r"""Creates a new ad watcher.

        :param player: Current player to watch ads for
        :type player: dict
        :param config: Configuration
        :type config: Config
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.player = player
        self.config = config
        self.log_info("New ad watcher({}). "
                      "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            self.player[Config.UUID],
            self.player[Config.STATS][Config.FULFILLED],
            self.player[Config.STATS][Config.UNFILLED],
            self.player[Config.STATS][Config.LIMIT_REACHED]
        ))

    def log_debug(self, msg):
        self.log.debug("[{}]: {}".format(self.player[Config.NAME], msg))

    def log_info(self, msg):
        self.log.info("[{}]: {}".format(self.player[Config.NAME], msg))

    def log_warning(self, msg):
        self.log.warning("[{}]: {}".format(self.player[Config.NAME], msg))

    def log_error(self, msg):
        self.log.error("[{}]: {}".format(self.player[Config.NAME], msg))

    def log_critical(self, msg):
        self.log.critical("[{}]: {}".format(self.player[Config.NAME], msg))

    @property
    def url(self):
        r"""The url of the ad.

        :return: Ad url
        :rtype: str
        """
        return "http://ad.desiredcraft.net/?server_id=44&player_uuid={}".format(self.player[Config.UUID])

    def setup(self):
        r"""Sets up the browser."""
        options = webdriver.ChromeOptions()
        # options = webdriver.FirefoxOptions()
        # profile = webdriver.FirefoxProfile()
        if self.config[Config.HEADLESS]:
            self.log_info("Using browser in headless mode.")
            options.add_argument("--headless")
        else:
            options.add_argument("--auto-open-devtools-for-tabs")
        if self.config[Config.INCOGNITO]:
            self.log_info("Using browser in incognito mode.")
            options.add_argument("--incognito")
            # profile.set_preference("browser.privatebrowsing.autostart", True)
            # profile.update_preferences()
        self.proxy = self.config.get_proxy()
        if self.proxy is not None:
            proxyurl = "{}:{}".format(self.proxy[Config.URL], self.proxy[Config.PORT])
            if not self.proxy[Config.USER] == "":
                proxyurl = "{}:{}@{}".format(self.proxy[Config.USER], self.proxy[Config.PASSWORD], proxyurl)
            proxyurl = "http://{}".format(proxyurl)
            # proxy = Proxy({
            #     'proxyType': ProxyType.MANUAL,
            #     'httpProxy': proxyurl,
            #     'ftpProxy': proxyurl,
            #     'sslProxy': proxyurl,
            #     'socksProxy': proxyurl,
            #     'noProxy': '',  # set this value as desired
            #     'socksUsername': self.proxy[Config.USER],
            #     'socksPassword': self.proxy[Config.PASSWORD]
            # })
            # profile.set_preference("network.proxy.type", 1)
            # profile.set_preference("network.proxy.http", self.proxy[Config.URL])
            # profile.set_preference("network.proxy.http_port", self.proxy[Config.PORT])
            # profile.set_preference("network.proxy.httpUsername", self.proxy[Config.USER])
            # profile.set_preference("network.proxy.httpPassword", self.proxy[Config.PASSWORD])
            # profile.set_preference("network.proxy.ssl", self.proxy[Config.URL])
            # profile.set_preference("network.proxy.ssl_port", self.proxy[Config.PORT])
            # profile.set_preference("network.proxy.sslUsername", self.proxy[Config.USER])
            # profile.set_preference("network.proxy.sslPassword", self.proxy[Config.PASSWORD])
            # profile.set_preference("network.proxy.socks", self.proxy[Config.URL])
            # profile.set_preference("network.proxy.socks_port", self.proxy[Config.PORT])
            # profile.set_preference("network.proxy.socksUsername", self.proxy[Config.USER])
            # profile.set_preference("network.proxy.socksPassword", self.proxy[Config.PASSWORD])
            # profile.set_preference("network.proxy.share_proxy_settings", True)
            # profile.set_preference('signon.autologin.proxy', True)

            # profile.set_preference('signon.autofillForms', True)
            # profile.set_preference('network.automatic-ntlm-auth.allow-proxies', False)
            # profile.set_preference('network.auth.use-sspi', False)
            # profile.update_preferences()
            options.add_argument("--proxy-server={}".format(proxyurl))
            self.log_info("Using proxy {}.".format(proxyurl))
            # proxyurl = self.proxy[Config.URL]
            # if not self.proxy[Config.USER] == '':
            #     user = self.proxy[Config.USER]
            #     self.log.debug("{}: Using proxy {} as {}. "
            #                    "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            #         self.player[Config.NAME],
            #         proxyurl,
            #         user,
            #         self.proxy[Config.STATS][Config.FULFILLED],
            #         self.proxy[Config.STATS][Config.UNFILLED],
            #         self.proxy[Config.STATS][Config.LIMIT_REACHED]
            #     ))
            #     proxyurl = "{}:{}@{}".format(user, self.proxy[Config.PASSWORD], proxyurl)
            # else:
            #     self.log.debug("{}: Using proxy {}. "
            #                    "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            #         self.player[Config.NAME],
            #         proxyurl,
            #         self.proxy[Config.STATS][Config.FULFILLED],
            #         self.proxy[Config.STATS][Config.UNFILLED],
            #         self.proxy[Config.STATS][Config.LIMIT_REACHED]
            #     ))
        # self.browser = webdriver.Firefox(firefox_profile=profile, options=options, proxy=proxy)
        # self.log.info(options.arguments)
        if os.path.exists('chromedriver.exe'):
            self.browser = webdriver.Chrome(options=options, executable_path='chromedriver.exe')
        else:
            self.browser = webdriver.Chrome(options=options)

    def does_proxy_work(self):
        r"""Checks whether the net unabandoned proxy in the list works or not.

        :return: Assessment of proxy
        :rtype: bool
        """
        if self.proxy is None:
            self.log.info("No more proxies to test. Relying on direct connection.")
            return True
        if self.proxy[Config.ABANDONED]:
            self.log.info("Proxy has been marked as abandoned. Reloading browser with new proxy settings.")
            self.quit()
            self.setup()
        self.browser.set_page_load_timeout(5)
        try:
            self.browser.get("https://ipinfo.io/json")
        except TimeoutException:
            self.proxy[Config.ABANDONED] = True
            self.log.info("Timeout exceeded. Abandoning proxy.")
            return False
        # self.browser.get("https://www.google.ch/")
        # WebDriverWait(self.browser, 30).until(expected_conditions.alert_is_present())
        # alert = self.browser.switch_to.alert
        # # The proxy moz-proxy://us2082.nordvpn.com:80 is requesting a username and password. The site says: “NordVPN”
        # if alert.text.startswith("The proxy"):
        #     self.log.info("Proxy alert found.")
        #     alert.send_keys("nothing")
        #     alert.send_keys(Keys.TAB)
        #     alert.send_keys("user")
        #     alert.send_keys(Keys.TAB)
        #     alert.send_keys("pw")
        try:
            WebDriverWait(self.browser, 1).until(
                expected_conditions.presence_of_element_located((By.CLASS_NAME, 'error-code')))
            elem = self.browser.find_element_by_class_name('error-code')
            self.log.warning("Error: {}".format(elem.text))
            self.proxy[Config.ABANDONED] = True
            self.log.info("Abandoning proxy.")
            return False
        except TimeoutException:
            pass
        # WebDriverWait(self.browser, 5).until(
        #     expected_conditions.((By.ID, 'rawdata-panel')))
        try:
            WebDriverWait(self.browser, 5).until(
                expected_conditions.presence_of_element_located((By.XPATH, '//html/body/pre')))
        except TimeoutException:
            self.log.info("No data in response. Abandoning proxy.")
            return False
        self.log.info('Proxy seems to work as expected.')
        el = self.browser.find_element_by_xpath('//html/body/pre')
        data = json.loads(el.text)
        self.log.info("Address: {}, Country: {}({}), Location: {}".format(
            data['ip'],
            data['country'],
            data['region'],
            data['loc']
        ))
        return True

    def is_limit_expired(self):
        r"""Checks whether the expiration limit has already passed

        :rtype: bool
        """
        last_limit = parser.parse(self.player[Config.LAST_LIMIT])
        limit_delay = timedelta(minutes=self.config[Config.LIMIT_DELAY])
        expire = last_limit + limit_delay
        if expire < datetime.now():
            return True
        else:
            delta = expire - datetime.now()
            self.log_warning("Limit({}) has not yet been reached. {} left.".format(expire, delta))
            return False

    class wait_for_opacity(object):
        def __call__(self, driver):
            try:
                fulfill = expected_conditions._find_element(driver, (By.ID, 'post-message'))
                unfill = expected_conditions._find_element(driver, (By.ID, 'no-fill-message'))
                maxed = expected_conditions._find_element(driver, (By.ID, 'max-view-message'))
                adblock = expected_conditions._find_element(driver, (By.ID, 'adblock-message-container'))
                if fulfill.value_of_css_property("opacity") == "1":
                    return True
                if unfill.value_of_css_property("opacity") == "1":
                    return True
                if maxed.value_of_css_property("opacity") == "1":
                    return True
                if adblock.value_of_css_property("opacity") == "1":
                    return True
                return False
            except StaleElementReferenceException:
                return False

    def watch(self):
        r"""Tries to watch one ad.

        :return: Result class for use in the stats dict
        :rtype: str
        """
        if self.proxy is not None and self.proxy[Config.ABANDONED]:
            self.log_info("Proxy has been marked as abandoned. Reloading browser with new proxy settings.")
            self.setup()
            while not self.does_proxy_work():
                self.quit()
                self.setup()
        self.browser.get(self.url)
        try:
            WebDriverWait(self.browser, 10).until(
                expected_conditions.presence_of_element_located((By.ID, 'player-wrapper'))
            )
        except TimeoutException:
            self.log_warning("Didn't recieve expected response.")
            return Config.UNFILLED
        except UnexpectedAlertPresentException:
            alert = self.browser.switch_to.alert
            self.log_warning("ALERT: {}".format(alert.text))
            alert.accept()
            self.log_warning("Limit not yet expired!")
            return Config.LIMIT_REACHED
        WebDriverWait(self.browser, 120).until(
            self.wait_for_opacity()
            # expected_conditions.presence_of_element_located((By.TAG_NAME, 'style'))
            # expected_conditions.presence_of_element_located((By.ID, 'max-view-message'))
        )
        fulfill = self.browser.find_element_by_id('post-message')
        unfill = self.browser.find_element_by_id('no-fill-message')
        maxed = self.browser.find_element_by_id('max-view-message')
        adblock = self.browser.find_element_by_id('adblock-message-container')
        if len(fulfill.get_property('style')) == 1:
            return Config.FULFILLED
        if len(unfill.get_property('style')) == 1:
            return Config.UNFILLED
        if len(maxed.get_property('style')) == 1:
            return Config.LIMIT_REACHED
        if len(adblock.get_property('style')) == 1:
            return ""
        self.log_critical("Couldn't determine the outcome!")
        exit(1)

    def watch_all(self):
        r"""Tries to watch ads until the limit has been reached."""
        unfilled_count = 0
        temp_stats = {
            Config.FULFILLED: 0,
            Config.UNFILLED: 0,
            Config.LIMIT_REACHED: 0
        }
        while True:
            try:
                result = self.watch()
                if not result == "":
                    self.player[Config.STATS][result] += 1
                    if self.proxy is not None:
                        self.proxy[Config.STATS][result] += 1
                    temp_stats[result] += 1
                else:
                    if self.proxy is not None:
                        self.proxy[Config.ABANDONED] = True
                        self.log_info("Website thinks I'm using adblock. Baka. Switching proxy.")
                    else:
                        self.log_critical("Website thinks I'm using adblock.")
                        return
            finally:
                self.log_debug("Saving config after watching.")
                self.config.save()
            if self.config.interrupt_save:
                self.quit()
                return
            if result == Config.UNFILLED and self.proxy is not None:
                unfilled_count += 1
                if unfilled_count >= self.config[Config.ABANDON_AFTER]:
                    self.proxy[Config.ABANDONED] = True
                    unfilled_count = 0
                    self.log_info("No ads received since {} tries. Abandoning proxy.".format(
                        self.config[Config.ABANDON_AFTER]
                    ))
            else:
                unfilled_count = 0
            if result == Config.LIMIT_REACHED:
                break
            interval = timedelta(seconds=self.config[Config.WATCH_DELAY])
            next_watch = datetime.now() + interval
            self.log_info("{} - Waiting until {}(in {}).".format(
                result.upper(),
                next_watch,
                interval
            ))
            try:
                time.sleep((next_watch - datetime.now()).total_seconds())
            finally:
                self.log_debug("Saving config after waiting.")
                self.config.save()
            if self.config.interrupt_save:
                self.quit()
                return
        self.player[Config.LAST_LIMIT] = datetime.now().isoformat()
        self.config.save()
        self.log_info("Reached maximum ad view count."
                      "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            temp_stats[Config.FULFILLED],
            temp_stats[Config.UNFILLED],
            temp_stats[Config.LIMIT_REACHED]
        ))
        self.quit()

    def quit(self):
        r"""Quits the currently used browser."""
        self.browser.quit()


class WebClient:
    r"""Web client to make HTTP requests to the internet"""
    log = None
    http = None
    headers = None
    cookies = {}
    proxy = {}

    def __init__(
            self,
            proxy='',
            user='',
            password='',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/68.0.3440.106 Safari/537.36 '
    ):
        r"""Creates a new web client.

        :param proxy: Proxy configuration by protocol
        :type proxy: dict
        :param user: Proxy user name
        :type user: str
        :param password: Proxy password
        :type password: str
        :param user_agent: user agent to use when making requests.
        :type user_agent: str
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.headers = {
            'Connection': 'keep-alive',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-GB,en;q=0.7,de;q=0.3',
            'DNT': '1',
            'User-Agent': user_agent,
            'Upgrade-Insecure-Requests': '1'
        }
        if proxy is not None and not proxy == '':
            self.log.info("Using proxy server {}".format(proxy))
            if not user == '':
                proxy = "{}:{}@{}".format(user, password, proxy)
            self.proxy = {
                "http": proxy,
                "https": proxy
            }
        self.log.debug("Set up web client.")

    def get(self, url, headers=None):
        r"""Sends a GET request to a url.

        :param url: Target address to send the request to
        :type url: str
        :param headers: Custom headers to use when making the request
        :type headers: dict
        :return: Response to the HTTP request
        :rtype: Response
        """
        if headers is None:
            headers = self.headers
        self.log.debug("GET: Requesting {}".format(url))
        response = requests.get(
            url,
            headers=headers,
            proxies=self.proxy
        )
        self.log.debug("GET: Recieved response to {}".format(url))
        return response

    def post(self, url, data, headers=None):
        r"""Sends a POST request to a url.

        :param url: Target address to send the request to
        :type url: str
        :param data: The data to send
        :type data: str
        :param headers: Custom headers to use when making the request
        :type headers: dict
        :return: Response to the HTTP request
        :rtype: Response
        """
        if headers is None:
            headers = self.headers
        self.log.debug("POST: Requesting {}".format(url))
        response = requests.post(
            url,
            headers=headers,
            proxies=self.proxy,
            body=json.dumps(data)
        )
        self.log.debug("POST: Recieved response to {}".format(url))
        return response

    def patch(self, url, data, headers=None):
        r"""Sends a PATCH request to a url.

        :param url: Target address to send the request to
        :type url: str
        :param data: The data to send
        :type data: str
        :param headers: Custom headers to use when making the request
        :type headers: dict
        :return: Response to the HTTP request
        :rtype: Response
        """
        if headers is None:
            headers = self.headers
        self.log.debug("PATCH: Requesting {}".format(url))
        response = requests.patch(
            url,
            headers=headers,
            proxies=self.proxy,
            body=json.dumps(data)
        )
        self.log.debug("PATCH: Recieved response to {}".format(url))
        return response


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


if __name__ == '__main__':
    Main().run()
