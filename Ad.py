import logging
from datetime import datetime, timedelta
from enum import Enum
from threading import Event

import dateparser
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, \
    UnexpectedAlertPresentException, NoAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from Browser import ChromeBrowserFactory, FirefoxBrowserFactory
from Configuration import Configuration, Keys


class AdWatcher():
    """Handles the watching of ads for a specific player."""
    log = None
    player = None
    config = None
    proxy = None
    browser = None
    browser_factory = None
    temp_stats = {
        Keys.FULFILLED: 0,
        Keys.UNFILLED: 0
    }
    continued_unfilleds = 0
    got_first_fullfilled = False
    interval = None

    def __init__(self, player, config):
        """Creates a new ad watcher.

        :param player: Current player to watch ads for
        :type player: dict
        :param config: Configuration
        :type config: Configuration
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.player = player
        self.config = config
        self.interval = timedelta(seconds=self.config[Keys.WATCH_DELAY])
        if config[Keys.BROWSER] == 'firefox':
            self.browser_factory = FirefoxBrowserFactory()
        elif config[Keys.BROWSER] == 'chrome':
            self.browser_factory = ChromeBrowserFactory()
        else:
            self.log_error("Unknown browser type: {}".format(config[Keys.BROWSER]))

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

    def print_statistics(self):
        self.log_info("Statistics(temp): Fulfilled({}), Unfilled({})".format(
            self.temp_stats[Keys.FULFILLED],
            self.temp_stats[Keys.UNFILLED]
        ))
        self.log_info("Statistics(total): Fulfilled({}), Unfilled({})".format(
            self.player[Keys.STATS][Keys.FULFILLED],
            self.player[Keys.STATS][Keys.UNFILLED]
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
        self.browser.set_page_load_timeout(self.config[Keys.PAGE_LOAD_TIMEOUT])
        self.browser.set_script_timeout(self.config[Keys.SCRIPT_TIMEOUT])
        self.log_info("Setup complete({}).".format(self.player[Keys.UUID]))

    def change_proxy(self):
        """Changes the current proxy

        :return: True if attempt was successful. False otherwise
        :rtype: bool
        """
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
        data = self.browser_factory.test_connection(self.browser, self.config[Keys.PAGE_LOAD_TIMEOUT])
        if data is None:
            self.proxy[Keys.ABANDONED] = True
            self.log.info("Abandoning proxy.")
            return False
        self.log.info("Connection established.")
        return True

    def get_time_span_until_limit_expires(self):
        """Calculate the time span left until the limit expires.

        :return: The time span until the limit expires. Negative if
        :rtype: timedelta
        """
        last_limit = dateparser.parse(self.player[Keys.LAST_LIMIT])
        limit_delay = timedelta(minutes=self.config[Keys.LIMIT_DELAY])
        return (last_limit + limit_delay) - datetime.now()

    def is_limit_expired(self):
        """Checks whether the expiration limit has already passed.

        :return: Whether the expiration date is already over
        :rtype: bool
        """
        time_left = self.get_time_span_until_limit_expires()
        if time_left < timedelta(0):
            return True
        else:
            expiration_date = datetime.now() + time_left
            self.log_warning("Limit({}) has not yet been reached. {} left.".format(expiration_date, time_left))
            return False

    def watch(self):
        """Tries to watch one ad.
        :return: Outcome of the try
        :rtype: WatchResults
        """
        if not self._check_proxy_still_valid():
            self.log_info("Proxy {} has been marked as abandoned. Changing to new proxy settings.".format(
                self.proxy[Keys.ADDRESS]
            ))
            self._change_proxy()

        result = self._load_ad_website()
        if result is not None:
            return result

        result = self._catch_premature_flags()
        if result is not None:
            return result

        result = self._await_end_of_ad()
        if result is not None:
            return result

        return self._classify_outcome()

    def _check_proxy_still_valid(self):
        """Make sure the proxy is still valid. if not, change to a valid proxy or revert back to DIRECT."""
        return self.proxy is None or not self.proxy[Keys.ABANDONED]

    def _change_proxy(self):
        """Change proxy settings"""
        while not self.does_proxy_work():
            if not self.change_proxy():
                break

    def _load_ad_website(self):
        """Load the ad website.

        :return: Successful or not
        :rtype: bool
        """
        try:
            self.browser.set_page_load_timeout(self.config[Keys.PAGE_LOAD_TIMEOUT])
            if self.browser.current_url == self.url:
                self.browser.refresh()
            else:
                self.browser.get(self.url)
            return None
        except TimeoutException:
            self.log.info("Timeout exceeded.")
            return WatchResults.TIMEOUT
        except:
            return WatchResults.INTERRUPTED

    def _catch_premature_flags(self):
        """Catch premature flags which indicate failure to watch ads.

        :return: Empty string if everything went normally. Result string otherwise.
        :rtype: WatchResults
        """
        try:
            WebDriverWait(self.browser, self.config[Keys.PAGE_LOAD_TIMEOUT]).until(
                expected_conditions.presence_of_element_located((By.ID, 'player-wrapper'))
            )
        except TimeoutException:
            self.log_error("Couldn't find 'player-wrapper'.")
            return WatchResults.ELEMENT_NOT_FOUND
        except UnexpectedAlertPresentException:
            try:
                alert = self.browser.switch_to.alert
            except NoAlertPresentException:
                self.log_error("Error reading supposed alert. Assuming limit reached.")
                return WatchResults.LIMIT_REACHED
            limit_reached_msg = "You have reached the maximum number of ad views per day. Further views are not " \
                                "permitted to prevent fraudulent activity. Please try again tomorrow."
            if alert.text == limit_reached_msg:
                alert.accept()
                self.log_warning("Limit not yet expired!")
                return WatchResults.LIMIT_REACHED
            self.log_warning("UNKNOWN ALERT: {}".format(alert.text))
            alert.accept()
            return WatchResults.UNDETERMINABLE
        except:
            return WatchResults.INTERRUPTED
        return None

    def _await_end_of_ad(self):
        """Wait until the ad has been watched.

        :return: Empty string if everything went normally. Result string otherwise.
        :rtype: WatchResults
        """

        class wait_for_opacity(object):
            def __call__(self, driver):
                try:
                    # After watching the ad, the one element that gets opacity defines the outcome.
                    fulfill = expected_conditions._find_element(driver, (By.ID, 'post-message'))
                    unfill = expected_conditions._find_element(driver, (By.ID, 'no-fill-message'))
                    maxed = expected_conditions._find_element(driver, (By.ID, 'max-view-message'))
                    adblock = expected_conditions._find_element(driver, (By.ID, 'adblock-message-container'))
                    # The element with the opacity == 1 is the one showing on top of the player.
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
        try:
            WebDriverWait(self.browser, self.config[Keys.AD_TIMEOUT]).until(wait_for_opacity())
            return None
        except TimeoutException:
            self.log_error("Timeout while awaiting end of ad.")
            return WatchResults.TIMEOUT
        except:
            return WatchResults.INTERRUPTED

    def _classify_outcome(self):
        """Classify the outcome of the ad watching.

        :return: Result
        :rtype: WatchResults
        """
        # Sometimes not everything gets loaded.
        # In that case, we just wait until the we see the css having loaded for the player.
        playerframe = self.browser.find_element_by_id('player-frame')
        if not playerframe.value_of_css_property("z-index") == "1":
            return WatchResults.NOT_LOADED
        fulfill = self.browser.find_element_by_id('post-message')
        unfill = self.browser.find_element_by_id('no-fill-message')
        maxed = self.browser.find_element_by_id('max-view-message')
        adblock = self.browser.find_element_by_id('adblock-message-container')
        if fulfill.value_of_css_property('opacity') == "1":
            return WatchResults.FULFILLED
        if unfill.value_of_css_property('opacity') == "1":
            return WatchResults.UNFILLED
        if maxed.value_of_css_property('opacity') == "1":
            return WatchResults.LIMIT_REACHED
        if adblock.value_of_css_property('opacity') == "1":
            return WatchResults.ADBLOCK
        self.log_error("Couldn't determine the outcome!")
        return WatchResults.UNDETERMINABLE

    def watch_all(self, event):
        """Tries to watch ads until the limit has been reached.

        :param event: Thread event object to control thread
        :type event: Event
        """
        self.continued_unfilleds = 0
        self.got_first_fullfilled = False
        while True:
            result = self.watch()
            self._update_stats(result)
            self.config.save()
            if not self._can_continue(result):
                break
            if self.proxy is not None and result in [WatchResults.UNFILLED, WatchResults.NOT_LOADED]:
                self._check_miss_count()
            now = datetime.now()
            next_watch = now + self.interval
            self.log_info("{} - Waiting until {}(in {}).".format(
                result.value.upper(),
                next_watch,
                self.interval
            ))
            event.wait((next_watch - now).total_seconds())
            if event.is_set():
                self.log_info("Shutting down...")
                self.print_statistics()
                self.quit()
                return
        self.config.save()
        self.log_info("Stopped ad watching.")
        self.print_statistics()

    def _update_stats(self, result):
        """Updates the statistics.

        :param result: The result to consume
        :type result: WatchResults
        """
        if result == WatchResults.FULFILLED:
            self.temp_stats[Keys.FULFILLED] += 1
            if self.proxy is not None:
                self.proxy[Keys.STATS][Keys.FULFILLED] += 1
        elif result == WatchResults.UNFILLED:
            self.temp_stats[Keys.UNFILLED] += 1
            if self.proxy is not None:
                self.proxy[Keys.STATS][Keys.UNFILLED] += 1

    def _clear_temp_statistics(self):
        self.temp_stats = {
            Keys.FULFILLED: 0,
            Keys.UNFILLED: 0
        }

    def _can_continue(self, result):
        """Decides whether continued ad watching is feasible or not.

        :param result: The result to base the decision on
        :type result: WatchResults
        :return: True if continued watching is feasible
        :rtype: bool
        """
        if result == WatchResults.LIMIT_REACHED:
            self.player[Keys.LAST_LIMIT] = datetime.now().isoformat()
            self.log_info("Reached the daily limit.")
            return False
        elif result == WatchResults.ADBLOCK:
            self.log_error("Website thinks I'm using adblock.")
            # if self.proxy is not None:
            #     self.proxy[Keys.ABANDONED] = True
            #     self.config.save()
            #     self.log_error("Switching proxy.")
            return True
        elif result == WatchResults.NOT_LOADED:
            self.log_error("Website didn't load properly.")
            return True
        elif result == WatchResults.UNDETERMINABLE:
            self.log_error("Couldn't determine the outcome.")
            return False
        elif result == WatchResults.TIMEOUT:
            self.log_error("A timeout occurred.")
            return False
        elif result == WatchResults.ELEMENT_NOT_FOUND:
            self.log_error("A HTML element couldn't be found.")
            return False
        elif result == WatchResults.INTERRUPTED:
            self.log_error("Recieved an interrupt signal.")
            return False
        return True

    def _check_miss_count(self):
        """Checks whether the proxy should be abandoned based on the continued unfilled counts."""
        if self.got_first_fullfilled:
            self.continued_unfilleds = 0
        else:
            self.continued_unfilleds += 1
            if self.continued_unfilleds >= self.config[Keys.ABANDON_AFTER]:
                self.proxy[Keys.ABANDONED] = True
                self.continued_unfilleds = 0
                self.log_info("No ads received since {} tries. Abandoning proxy.".format(
                    self.config[Keys.ABANDON_AFTER]
                ))
                self.got_first_fullfilled = False

    def ad_grind_forever(self, event):
        """Keep watching ads forever.

        :param event: Thread event object to control thread
        :type event: Event
        """
        while True:
            if not self.is_limit_expired():
                time_left = self.get_time_span_until_limit_expires()
                self.log_info("Waiting until ad limit expires(in {})".format(time_left))
                event.wait(time_left.total_seconds())
                if event.is_set():
                    self.log_info("Ending infinity loop.")
                    self.print_statistics()
                    self.quit()
                    break
            self._clear_temp_statistics()
            self.watch_all(event)
            if event.is_set():
                break

    def quit(self):
        """Quits the currently used browser."""
        self.browser.quit()


class WatchResults(Enum):
    FULFILLED = Keys.FULFILLED
    UNFILLED = Keys.UNFILLED
    LIMIT_REACHED = Keys.LIMIT_REACHED
    TIMEOUT = "Timeout"
    ELEMENT_NOT_FOUND = "Element not found"
    UNDETERMINABLE = "Undeterminable result"
    ADBLOCK = "Adblock"
    INTERRUPTED = "Interrupted"
    NOT_LOADED = "Website not properly loaded"
