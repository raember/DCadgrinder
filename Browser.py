import logging
import platform
import json
from selenium.webdriver import Firefox, FirefoxOptions, FirefoxProfile
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.proxy import ProxyType
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By


class BrowserFactory:
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    def _log_headless(self):
        self.log.debug("Using headless mode.")

    def _log_devtools(self):
        self.log.debug("Using dev tools.")

    def _log_incognito(self):
        self.log.debug("Using incognito mode.")

    def _log_proxy(self, proxy_address):
        """
        :param proxy_address: The proxy address to log
        :type proxy_address: str
        """
        self.log.debug("Using proxy to connect: {}".format(proxy_address))

    def create(self, headless=False, devtools=False, incognito=False, proxy_url='', proxy_port=80):
        """Creates a browser.

        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: A fully prepared browser
        :rtype: WebDriver
        """
        raise NotImplementedError('Method has to be overwritten by a subclass.')

    def change_proxy(self, browser, headless=False, devtools=False, incognito=False, proxy_url='', proxy_port=80):
        """Changes the proxy configuration.

        :param browser: Browser
        :type browser: WebDriver
        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: Browser with a renewed proxy configuration
        :rtype: WebDriver
        """
        raise NotImplementedError('Method has to be overwritten by a subclass.')

    def test_connection(self, browser, timeout):
        """Test connection to the internet.

        :param browser: Browser
        :type browser: WebDriver
        :param timeout: Timeout in seconds after which the connection is deemed unusable
        :type timeout: int
        :return: The information from the connection or None if no connection could be established
        :rtype: dict
        """
        browser.set_page_load_timeout(timeout)
        try:
            browser.get("https://ipinfo.io/json")
        except TimeoutException:
            self.log.info("Timeout exceeded.")
            return None
        try:
            WebDriverWait(browser, 1).until(
                expected_conditions.presence_of_element_located((By.CLASS_NAME, 'error-code')))
            elem = browser.find_element_by_class_name('error-code')
            self.log.warning("Error: {}".format(elem.text))
            return None
        except TimeoutException:
            pass
        try:
            WebDriverWait(browser, 1).until(
                expected_conditions.presence_of_element_located((By.TAG_NAME, 'pre')))
        except TimeoutException:
            self.log.info("No data in response.")
            return None
        el = browser.find_element_by_tag_name('pre')
        data = json.loads(el.text)
        self.log.info("Address: {}, Country: {}({}), Location: {}".format(
            data['ip'],
            data['country'],
            data['region'],
            data['loc']
        ))
        return data


class ChromeBrowserFactory(BrowserFactory):
    def create(
            self,
            headless=False,
            devtools=False,
            incognito=False,
            proxy_url='',
            proxy_port=80
    ):
        """Creates a Chrome browser.

        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: A fully prepared Chrome browser
        :rtype: Chrome
        """
        options = ChromeOptions()
        if headless:
            options.headless = True
            self._log_headless()
        if devtools:
            options.add_argument("--auto-open-devtools-for-tabs")
            self._log_devtools()
        if incognito:
            options.add_argument("--incognito")
            self._log_incognito()
        if not proxy_url == '':
            proxy_address = "{}:{}".format(proxy_url, proxy_port)
            options.add_argument("--proxy-server={}".format(proxy_address))
            self._log_proxy(proxy_address)
        self.log.debug("Arguments: {}".format(options.arguments))
        if platform.system() == 'Windows':
            return Chrome(options=options, executable_path='chromedriver.exe')
        else:
            return Chrome(options=options)

    def change_proxy(
            self,
            browser,
            headless=False,
            devtools=False,
            incognito=False,
            proxy_url='',
            proxy_port=80
    ):
        """Changes the proxy configuration.

        :param browser: Browser
        :type browser: Chrome
        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: Chrome with a renewed proxy configuration
        :rtype:Chrome
        """
        browser.quit()
        return self.create(headless, devtools, incognito, proxy_url, proxy_port)


class FirefoxBrowserFactory(BrowserFactory):
    def create(
            self,
            headless=False,
            devtools=False,
            incognito=False,
            proxy_url='',
            proxy_port=80
    ):
        """Creates a Firefox browser.

        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: A fully prepared Firefox browser
        :rtype: Firefox
        """
        options = FirefoxOptions()
        profile = FirefoxProfile()
        options.profile = profile
        profile.set_preference("devtools.jsonview.enabled", False) # To parse JSON
        profile.set_preference("devtools.inspector.show-three-pane-tooltip", False) # Monopolizes focus
        # profile.set_preference("devtools.inspector.three-pane-first-run", False) # Monopolizes focus
        if headless:
            options.headless = True
            self._log_headless()
        if devtools:
            options.add_argument('-devtools')
            self._log_devtools()
        if incognito:
            profile.set_preference("browser.privatebrowsing.autostart", True)
            self._log_incognito()
        if not proxy_url == '':
            profile.set_preference("network.proxy.type", ProxyType.MANUAL['ff_value'])
            profile.set_preference("network.proxy.http", proxy_url)
            profile.set_preference("network.proxy.http_port", proxy_port)
            profile.set_preference("network.proxy.share_proxy_settings", True)
            proxy_address = "{}:{}".format(proxy_url, proxy_port)
            self._log_proxy(proxy_address)
        profile.update_preferences()
        self.log.debug("Arguments: {}".format(options.arguments))
        if platform.system() == 'Windows':
            return Firefox(options=options, executable_path='geckodriver.exe')
        else:
            return Firefox(options=options)

    def change_proxy(
            self,
            browser,
            headless=False,
            devtools=False,
            incognito=False,
            proxy_url='',
            proxy_port=80
    ):
        """Changes the proxy configuration.

        :param browser: Browser
        :type browser: Firefox
        :param headless: If the browser should start in headless mode
        :type headless: bool
        :param devtools: If the browser should start with opened dev tools
        :type devtools: bool
        :param incognito: If the browser should start in incognito mode
        :type incognito: bool
        :param proxy_url: The proxy url
        :type proxy_url: str
        :param proxy_port: The proxy port
        :type proxy_port: int
        :return: Firefox with a renewed proxy configuration
        :rtype:Firefox
        """
        browser.command_executor._commands["SET_CONTEXT"] = ("POST", "/session/$sessionId/moz/context")
        if not proxy_url == '':
            browser.execute("SET_CONTEXT", {"context": "chrome"})
            browser.execute_script("""
            Services.prefs.setIntPref('network.proxy.type', arguments[0]);
            Services.prefs.setStringPref('network.proxy.http', arguments[1]);
            Services.prefs.setIntPref('network.proxy.http_port', arguments[2]);
            Services.prefs.setBoolPref('network.proxy.share_proxy_settings', true);
            """, ProxyType.MANUAL['ff_value'], proxy_url, proxy_port)
            browser.execute("SET_CONTEXT", {"context": "content"})
            proxy_address = "{}:{}".format(proxy_url, proxy_port)
        else:
            browser.execute("SET_CONTEXT", {"context": "chrome"})
            browser.execute_script("""
            Services.prefs.setIntPref('network.proxy.type', arguments[0]);
            """, ProxyType.DIRECT['ff_value'])
            browser.execute("SET_CONTEXT", {"context": "content"})
            proxy_address = 'DIRECT'
        self._log_proxy(proxy_address)
        return browser
