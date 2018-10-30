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
        """Tries to watch one ad.

        :return: Result class for use in the stats dict
        :rtype: str
        """
        if self.proxy is not None and self.proxy[Keys.ABANDONED]:
            self.log_info("Proxy {} has been marked as abandoned. Changing to new proxy settings.".format(
                self.proxy[Keys.ADDRESS]
            ))
            while not self.does_proxy_work():
                if not self.change_proxy_successful():
                    break

        # Load site
        if self.browser.current_url == self.url:
            self.browser.refresh()
        else:
            self.browser.get(self.url)
        try:
            WebDriverWait(self.browser, 10).until(
                expected_conditions.presence_of_element_located((By.ID, 'player-wrapper'))
            )
        except TimeoutException:
            self.log_warning("Didn't recieve expected response.")
            return Keys.UNFILLED
        except UnexpectedAlertPresentException:
            alert = self.browser.switch_to.alert
            self.log_warning("ALERT: {}".format(alert.text))
            alert.accept()
            self.log_warning("Limit not yet expired!")
            return Keys.LIMIT_REACHED

        # Wait until ad has been watched
        try:
            WebDriverWait(self.browser, 120).until(
                self.wait_for_opacity()
                # expected_conditions.presence_of_element_located((By.TAG_NAME, 'style'))
                # expected_conditions.presence_of_element_located((By.ID, 'max-view-message'))
            )
        except TimeoutException:
            self.log_error("Timeout while awaiting end of ad.")
            exit(1)

        # Determine outcome
        fulfill = self.browser.find_element_by_id('post-message')
        unfill = self.browser.find_element_by_id('no-fill-message')
        maxed = self.browser.find_element_by_id('max-view-message')
        adblock = self.browser.find_element_by_id('adblock-message-container')
        if fulfill.value_of_css_property('opacity') == "1":
            return Keys.FULFILLED
        if unfill.value_of_css_property('opacity') == "1":
            return Keys.UNFILLED
        if maxed.value_of_css_property('opacity') == "1":
            return Keys.LIMIT_REACHED
        if adblock.value_of_css_property('opacity') == "1":
            return ""
        self.log_error("Couldn't determine the outcome!")
        exit(1)

    def watch_all(self):
        """Tries to watch ads until the limit has been reached."""
        unfilled_count = 0
        temp_stats = {
            Keys.FULFILLED: 0,
            Keys.UNFILLED: 0,
            Keys.LIMIT_REACHED: 0
        }
        while True:
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
        self.log_info("Reached maximum ad view count."
                      "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            temp_stats[Keys.FULFILLED],
            temp_stats[Keys.UNFILLED],
            temp_stats[Keys.LIMIT_REACHED]
        ))
        self.quit()

    def quit(self):
        """Quits the currently used browser."""
        self.browser.quit()