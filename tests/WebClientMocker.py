import json
import base64
from Web import WebClient


class Dynamic(object):
    pass


class FakeWebClient(WebClient):
    _entries = None

    def __init__(self, path):
        super().__init__()
        self.log.debug("Loading mock data from {}".format(path))
        with open(path) as json_data:
            self._entries = json.load(json_data)["log"]["entries"]
        self.log.debug("Loaded data({} entries)".format(len(self._entries)))

    def get(self, url, headers=None):
        for entry in self._entries:
            # if entry["request"]["url"].startswith(url.split('?')[0]):
            #     print(entry["request"]["url"])
            #     print(url)
            if entry["request"]["method"] == 'GET' and entry["request"]["url"] == url:
                self.log.debug("Found stored response to GET request {}".format(url))
                val = Dynamic()
                try:
                    val.content = base64.decodebytes(entry["response"]["content"]["text"].encode('utf-8'))
                except:
                    val.content = b""
                return val
        self.log.error("Couldn't match a saved response to the GET request to {}".format(url))
        raise Exception("Couldn't match a saved response to the GET request to {}".format(url))

    def post(self, url, data, headers=None):
        for entry in self._entries:
            if entry["request"]["method"] == 'POST' and entry["request"]["url"] == url:
                self.log.info("Found stored response to POST request.")
                val = Dynamic()
                try:
                    val.content = base64.decodebytes(entry["response"]["content"]["text"].encode('utf-8'))
                except:
                    val.content = b""
                return val
        self.log.error("Couldn't match a saved response to the POST request to {}".format(url))
        raise Exception("Couldn't match a saved response to the POST request to {}".format(url))

    def patch(self, url, data, headers=None):
        for entry in self._entries:
            if entry["request"]["method"] == 'PATCH' and entry["request"]["url"] == url:
                self.log.info("Found stored response to PATCH request.")
                val = Dynamic()
                try:
                    val.content = base64.decodebytes(entry["response"]["content"]["text"].encode('utf-8'))
                except:
                    val.content = b""
                return val
        self.log.error("Couldn't match a saved response to the PATCH request to {}".format(url))
        raise Exception("Couldn't match a saved response to the PATCH request to {}".format(url))
