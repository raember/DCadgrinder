import logging
import os
import json
import time
import dateparser
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta
from Configuration import Configuration, Keys
from Browser import ChromeBrowserFactory, FirefoxBrowserFactory

class AdWatcher():
    r"""Handles the watching of ads for a specific player."""
    log = None
    player = None
    config = None
    proxy = None
    browser = None
    browser_factory = None

    def __init__(self, player, config):
        r"""Creates a new ad watcher.

        :param player: Current player to watch ads for
        :type player: dict
        :param config: Configuration
        :type config: Configuration
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.player = player
        self.config = config
        if config[Keys.BROWSER] == 'firefox':
            self.browser_factory = FirefoxBrowserFactory()
        elif config[Keys.BROWSER] == 'chrome':
            self.browser_factory = ChromeBrowserFactory()
        else:
            self.log_error("Unknown browser type: {}".format(config[Keys.BROWSER]))
        self.log_info("New ad watcher({}).".format(self.player[Keys.UUID]))

    def log_debug(self, msg):
        self.log.debug("[{}]: {}".format(self.player[Keys.NAME], msg))

    def log_info(self, msg):
        self.log.info("[{}]: {}".format(self.player[Keys.NAME], msg))

    def log_warning(self, msg):
        self.log.warning("[{}]: {}".format(self.player[Keys.NAME], msg))

    def log_error(self, msg):
        self.log.error("[{}]: {}".format(self.player[Keys.NAME], msg))

    def log_critical(self, msg):
        self.log.critical("[{}]: {}".format(self.player[Keys.NAME], msg))

    def print_statistic(self):
        self.log_info("Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            self.player[Keys.STATS][Keys.FULFILLED],
            self.player[Keys.STATS][Keys.UNFILLED],
            self.player[Keys.STATS][Keys.LIMIT_REACHED]
        ))

    @property
    def url(self):
        """The url of the ad.

        :return: Ad url
        :rtype: str
        """
        return "http://ad.desiredcraft.net/?server_id=44&player_uuid={}".format(self.player[Keys.UUID])

    def setup(self):
        """Sets up the browser."""
        self.proxy = self.config.get_proxy()
        self.browser = self.browser_factory.create(
            self.config[Keys.HEADLESS],
            self.config[Keys.DEVTOOLS],
            self.config[Keys.INCOGNITO],
            "" if self.proxy is None else self.proxy[Keys.ADDRESS],
            80 if self.proxy is None else self.proxy[Keys.PORT]
        )

    def change_proxy_successful(self):
        """Changes the current proxy"""
        self.proxy = self.config.get_proxy()
        if self.proxy is None:
            return False
        self.browser = self.browser_factory.change_proxy(
            self.browser,
            self.config[Keys.HEADLESS],
            self.config[Keys.DEVTOOLS],
            self.config[Keys.INCOGNITO],
            "" if self.proxy is None else self.proxy[Keys.ADDRESS],
            80 if self.proxy is None else self.proxy[Keys.PORT]
        )
        return True

    def does_proxy_work(self):
        """Checks whether the net unabandoned proxy in the list works or not.

        :return: Assessment of proxy
        :rtype: bool
        """
        data = self.browser_factory.test_connection(self.browser, self.config[Keys.TIMEOUT])
        if data is None:
            self.proxy[Keys.ABANDONED] = True
            self.log.info("Abandoning proxy.")
            return False
        self.log.info("Connection established.")
        return True

    def is_limit_expired(self):
        r"""Checks whether the expiration limit has already passed

        :rtype: bool
        """
        last_limit = dateparser.parse(self.player[Keys.LAST_LIMIT])
        limit_delay = timedelta(minutes=self.config[Keys.LIMIT_DELAY])
        expire = last_limit + limit_delay
        now = datetime.now()
        if expire < now:
            return True
        else:
            self.log_warning("Limit({}) has not yet been reached. {} left.".format(expire, expire - now))
            return False

    def watch(self):
        """Tries to watch one ad.

        :return: Result class for use in the stats dict
        :rtype: str
        """
        if self.proxy is not None:
            self._check_proxy_still_valid()
        if not self._load_ad_website():
            exit(1)
        premature_result = self._catch_premature_flags()
        if not premature_result == '':
            return premature_result
        if not self._await_end_of_ad():
            exit(1)
        result = self._classify_outcome()
        if result is None:
            exit(1)
        return result

    def watch_all(self):
        """Tries to watch ads until the limit has been reached."""
        unfilled_count = 0
        temp_stats = {
            Keys.FULFILLED: 0,
            Keys.UNFILLED: 0,
            Keys.LIMIT_REACHED: 0
        }
        while True:
            result = ''
            try:
                result = self.watch()
                if not result == "":
                    self.player[Keys.STATS][result] += 1
                    if self.proxy is not None:
                        self.proxy[Keys.STATS][result] += 1
                    temp_stats[result] += 1
                else:
                    if self.proxy is not None:
                        self.proxy[Keys.ABANDONED] = True
                        self.log_info("Website thinks I'm using adblock. Baka. Switching proxy.")
                    else:
                        self.log_critical("Website thinks I'm using adblock.")
                        return
            except:
                self.log_error("Exception occurred. Idk what or why though. Please fix me.")
                exit(1)
            finally:
                self.log_debug("Saving config after watching.")
                self.config.save()
            if self.config.interrupt_save:
                self.quit()
                return
            if result == Keys.UNFILLED and self.proxy is not None:
                unfilled_count += 1
                if unfilled_count >= self.config[Keys.ABANDON_AFTER]:
                    self.proxy[Keys.ABANDONED] = True
                    unfilled_count = 0
                    self.log_info("No ads received since {} tries. Abandoning proxy.".format(
                        self.config[Keys.ABANDON_AFTER]
                    ))
            else:
                unfilled_count = 0
            if result == Keys.LIMIT_REACHED:
                break
            interval = timedelta(seconds=self.config[Keys.WATCH_DELAY])
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
        self.player[Keys.LAST_LIMIT] = datetime.now().isoformat()
        self.config.save()
        self.log_info("Reached maximum ad view count.")
        self.print_statistic()
        self.quit()

    def quit(self):
        """Quits the currently used browser."""
        self.browser.quit()
