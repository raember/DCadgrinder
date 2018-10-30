#!/usr/bin/env python3

import logging
import argparse
import os
import threading
import time
from Web import WebClient
from Configuration import Configuration, Keys
from Ad import AdWatcher
from GameApi import GameApi

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)16s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)


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
        conf = Configuration()
        if self.args.abandon_proxy:
            self.log.info('Marking current proxy as abandoned.')
            conf.load()
            proxy = conf.get_proxy()
            if proxy is None:
                self.log.info("No more proxies to abandon.")
            else:
                self.log.info("Abandoning {}.".format(proxy[Keys.URL]))
                proxy[Keys.ABANDONED] = True
                conf.save()
            exit(0)
        if self.args.delete_abandoned:
            self.log.info('Deleting abandoned proxies.')
            conf.load()
            for proxy in conf[Keys.PROXIES]:
                if proxy[Keys.ABANDONED]:
                    self.log.info("Deleting proxy {}.".format(proxy[Keys.URL]))
                    conf[Keys.PROXIES].remove(proxy)
            conf.save()
            exit(0)
        webclient = WebClient(os.getenv('HTTP_PROXY'))
        gameapi = GameApi(webclient)
        if self.args.create_config:
            self.log.info('Creating sample config file.')
            Configuration().complete_data(gameapi, 'Notch').save()
            exit(0)
        if self.args.update:
            self.log.info('Updating player names from UUIDs.')
            conf.load()
            for player in conf[Keys.PLAYERS]:
                if Keys.NAME in player:
                    del (player[Keys.NAME])
            conf.complete_data(gameapi)
            conf.save()
            exit(0)
        if self.args.test:
            self.log.info('Running proxy test.')
            conf.load().complete_data(gameapi)
            fake_player = {
                Keys.NAME: 'PROXY TEST',
                Keys.UUID: ''
            }
            watcher = AdWatcher(fake_player, conf)
            watcher.setup()
            while not watcher.does_proxy_work():
                watcher.quit()
                watcher.setup()
            watcher.quit()
            conf.save()
            exit(0)
        if self.args.reset:
            self.log.info('Resetting statistics.')
            conf.load().complete_data(gameapi)
            for player in conf[Keys.PLAYERS]:
                player[Keys.STATS] = {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}
            for proxy in conf[Keys.PROXIES]:
                proxy[Keys.STATS] = {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}
            conf.save()
            exit(0)

        # Let's go!
        conf.load().complete_data(gameapi).save()
        self.log.info("Watching ads for the following players: {}".format(
            ", ".join([player[Keys.NAME] for player in conf[Keys.PLAYERS]])))
        watcherthreads = []
        for player in conf[Keys.PLAYERS]:
            watcher = AdWatcher(player, conf)
            if watcher.is_limit_expired():
                watcher.setup()
                thread = threading.Thread(target=watcher.watch_all)
                thread.start()
                watcherthreads.append(thread)
                self.log.info("Started ad watcher thread. Waiting {}s.".format(conf[Keys.START_DELAY]))
                time.sleep(conf[Keys.START_DELAY])
        try:
            for thread in watcherthreads:
                thread.join()
        except KeyboardInterrupt:
            conf.save()
        self.log.info("Finished.")


if __name__ == '__main__':
    Main().run()
