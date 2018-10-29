import logging
import requests
import json

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