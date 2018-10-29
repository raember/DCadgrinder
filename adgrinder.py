#!/usr/bin/env python3

import logging
import argparse
import os
import threading
import time
from Web import WebClient
from Configuration import Configuration
from Ad import AdWatcher

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
        if self.args.create_config:
            self.log.info('Creating sample config file.')
            Configuration().create_example_config().save()
            exit(0)
        if self.args.abandon_proxy:
            self.log.info('Marking current proxy as abandoned.')
            conf = Configuration().load()
            proxy = conf.get_proxy()
            if proxy is None:
                self.log.info("No more proxies to abandon.")
            else:
                self.log.info("Abandoning {}.".format(proxy[Configuration.URL]))
                proxy[Configuration.ABANDONED] = True
                conf.save()
            exit(0)
        if self.args.delete_abandoned:
            self.log.info('Deleting abandoned proxies.')
            conf = Configuration().load()
            for proxy in conf[Configuration.PROXIES]:
                if proxy[Configuration.ABANDONED]:
                    self.log.info("Deleting proxy {}.".format(proxy[Configuration.URL]))
                    conf[Configuration.PROXIES].remove(proxy)
            conf.save()
            exit(0)
        webclient = WebClient(os.getenv('HTTP_PROXY'))
        if self.args.update:
            self.log.info('Updating player names from UUIDs.')
            conf = Configuration().load()
            for player in conf[Configuration.PLAYERS]:
                if Configuration.NAME in player:
                    del (player[Configuration.NAME])
            conf.complete_data(webclient)
            conf.save()
            exit(0)
        if self.args.test:
            self.log.info('Running proxy test.')
            conf = Configuration().load().complete_data(webclient)
            watcher = AdWatcher(conf[Configuration.PLAYERS][0], conf)
            watcher.setup()
            while not watcher.does_proxy_work():
                watcher.quit()
                watcher.setup()
            watcher.quit()
            conf.save()
            exit(0)
        if self.args.reset:
            self.log.info('Resetting statistics.')
            conf = Configuration().load().complete_data(webclient)
            for player in conf[Configuration.PLAYERS]:
                player[Configuration.STATS] = {Configuration.FULFILLED: 0, Configuration.UNFILLED: 0, Configuration.LIMIT_REACHED: 0}
            for proxy in conf[Configuration.PROXIES]:
                proxy[Configuration.STATS] = {Configuration.FULFILLED: 0, Configuration.UNFILLED: 0, Configuration.LIMIT_REACHED: 0}
            conf.save()
            exit(0)

        # Let's go!
        conf = Configuration().load().complete_data(webclient)
        conf.save()  # So we have a sexy formatted config file.
        self.log.info("Watching ads for the following players: {}".format(
            ", ".join([p[Configuration.NAME] for p in conf[Configuration.PLAYERS]])))
        watcherthreads = []
        for player in conf[Configuration.PLAYERS]:
            watcher = AdWatcher(player, conf)
            if watcher.is_limit_expired():
                watcher.setup()
                thread = threading.Thread(target=watcher.watch_all)
                thread.start()
                watcherthreads.append(thread)
                self.log.info("Started ad watcher thread. Waiting {}s.".format(conf[Configuration.START_DELAY]))
                time.sleep(conf[Configuration.START_DELAY])
        try:
            for thread in watcherthreads:
                thread.join()
        except KeyboardInterrupt:
            conf.save()
        self.log.info("Finished.")


if __name__ == '__main__':
    Main().run()
