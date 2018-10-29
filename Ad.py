import logging
import os
import json
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from dateparser import parser
from datetime import datetime, timedelta
from Configuration import Configuration, Keys

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
        :type config: Configuration
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.player = player
        self.config = config
        self.log_info("New ad watcher({}). "
                      "Statistics: Fulfilled({}), Unfilled({}), Limit reached({})".format(
            self.player[Keys.UUID],
            self.player[Keys.STATS][Keys.FULFILLED],
            self.player[Keys.STATS][Keys.UNFILLED],
            self.player[Keys.STATS][Keys.LIMIT_REACHED]
        ))

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

    @property
    def url(self):
        r"""The url of the ad.

        :return: Ad url
        :rtype: str
        """
        return "http://ad.desiredcraft.net/?server_id=44&player_uuid={}".format(self.player[Keys.UUID])

    def setup(self):
        r"""Sets up the browser."""
        options = webdriver.ChromeOptions()
        # options = webdriver.FirefoxOptions()
        # profile = webdriver.FirefoxProfile()
        if self.config[Keys.HEADLESS]:
            self.log_info("Using browser in headless mode.")
            options.add_argument("--headless")
        else:
            options.add_argument("--auto-open-devtools-for-tabs")
        if self.config[Keys.INCOGNITO]:
            self.log_info("Using browser in incognito mode.")
            options.add_argument("--incognito")
            # profile.set_preference("browser.privatebrowsing.autostart", True)
            # profile.update_preferences()
        self.proxy = self.config.get_proxy()
        if self.proxy is not None:
            proxyurl = "{}:{}".format(self.proxy[Keys.URL], self.proxy[Keys.PORT])
            # if not self.proxy[Keys.USER] == "":
            #     proxyurl = "{}:{}@{}".format(self.proxy[Keys.USER], self.proxy[Keys.PASSWORD], proxyurl)
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
        if self.proxy[Keys.ABANDONED]:
            self.log.info("Proxy has been marked as abandoned. Reloading browser with new proxy settings.")
            self.quit()
            self.setup()
        self.browser.set_page_load_timeout(5)
        try:
            self.browser.get("https://ipinfo.io/json")
        except TimeoutException:
            self.proxy[Keys.ABANDONED] = True
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
            self.proxy[Keys.ABANDONED] = True
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
        last_limit = parser.parse(self.player[Keys.LAST_LIMIT])
        limit_delay = timedelta(minutes=self.config[Keys.LIMIT_DELAY])
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
        if self.proxy is not None and self.proxy[Keys.ABANDONED]:
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
            return Keys.UNFILLED
        except UnexpectedAlertPresentException:
            alert = self.browser.switch_to.alert
            self.log_warning("ALERT: {}".format(alert.text))
            alert.accept()
            self.log_warning("Limit not yet expired!")
            return Keys.LIMIT_REACHED
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
            return Keys.FULFILLED
        if len(unfill.get_property('style')) == 1:
            return Keys.UNFILLED
        if len(maxed.get_property('style')) == 1:
            return Keys.LIMIT_REACHED
        if len(adblock.get_property('style')) == 1:
            return ""
        self.log_critical("Couldn't determine the outcome!")
        exit(1)

    def watch_all(self):
        r"""Tries to watch ads until the limit has been reached."""
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
        r"""Quits the currently used browser."""
        self.browser.quit()