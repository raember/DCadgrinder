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
    """Main program. Manages ad watchers in parallel."""
    log = None
    args = None
    conf = Configuration()

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
                            help="Test connection and exit.")
        parser.add_argument('-a', '--abandon-proxy', action='store_true',
                            help="Abandon current proxy server and exit.")
        parser.add_argument('-s', '--statistics', action='store_true',
                            help="Print statistics and exit.")
        self.args = parser.parse_args()

    def run(self):
        if self.args.abandon_proxy:
            if not self.abandon_proxy():
                exit(1)
            exit(0)
        if self.args.delete_abandoned:
            self.delete_abandoned_proxies()
            exit(0)
        if self.args.create_config:
            if not self.create_sample_config():
                exit(1)
            exit(0)
        if self.args.update:
            self.delete_abandoned_proxies()
            exit(0)
        if self.args.test:
            if not self.test_connection():
                exit(1)
            exit(0)
        if self.args.reset:
            self.reset_statistics()
            exit(0)
        if self.args.statistics:
            self.print_statistics()
            exit(0)

        # Let's go!
        self.conf.load().complete_data(self.create_gameapi()).save()
        self.log.info("Watching ads for the following players: {}".format(
            ", ".join([player[Keys.NAME] for player in self.conf[Keys.PLAYERS]])))
        watcherthreads = []
        for player in self.conf[Keys.PLAYERS]:
            watcher = AdWatcher(player, self.conf)
            if watcher.get_time_until_limit_expires():
                watcher.setup()
                thread = threading.Thread(target=watcher.watch_all)
                thread.start()
                watcherthreads.append(thread)
                self.log.info("Started ad watcher thread. Waiting {}s.".format(self.conf[Keys.START_DELAY]))
                time.sleep(self.conf[Keys.START_DELAY])
        try:
            for thread in watcherthreads:
                thread.join()
        except KeyboardInterrupt:
            self.conf.save()
        self.log.info("Finished.")

    def create_gameapi(self):
        """Creates a GameApi instance

        :return: The GameApi instance
        :rtype: GameApi
        """
        return GameApi(WebClient(os.getenv('HTTP_PROXY')))

    def abandon_proxy(self):
        """Abandons the current proxy. Will ask for confirmation.

        :return: Whether the procedure was successful
        :rtype: bool
        """
        self.conf.load()
        proxy = self.conf.get_proxy()
        if proxy is None:
            self.log.info("There is no proxy to abandon.")
            return False
        answer = input("Abandon proxy {}:{}? [y/N]".format(proxy[Keys.ADDRESS], proxy[Keys.PORT])).lower()
        if answer == 'y':
            self.log.info('Marking current proxy as abandoned.')
            proxy[Keys.ABANDONED] = True
            self.conf.save()
        else:
            self.log.info("Nothing to do.")
            return True

    def delete_abandoned_proxies(self):
        """Deletes all proxies from the list that are marked as abandoned."""
        deleted_proxies = False
        self.conf.load()
        for proxy in self.conf[Keys.PROXIES]:
            if proxy[Keys.ABANDONED]:
                deleted_proxies = True
                self.log.info("Deleting proxy {}:{}".format(proxy[Keys.ADDRESS], proxy[Keys.PORT]))
                self.conf[Keys.PROXIES].remove(proxy)
        if not deleted_proxies:
            self.log.info("There were no proxies to delete.")
            self.conf.save()

    def create_sample_config(self):
        """Creates a sample config file. Asks before overwriting.

        :return: Whether the procedure was successful
        :rtype: bool
        """
        notchs_uuid = '069a79f4-44e9-4726-a5be-fca90e38aaf5'
        if os.path.exists(self.conf.filename):
            answer = input("There already exists a config file. Do you want to delete it? [y/N]").lower()
            if not answer == 'y':
                self.log.info("Nothing to do.")
                return False
        self.log.info('Creating sample config file.')
        Configuration().complete_data(self.create_gameapi(), notchs_uuid).save()
        return True

    def update_usernames(self):
        """Updates usernames"""
        self.log.info('Updating player names from UUIDs.')
        self.conf.load().complete_data(self.create_gameapi(), reload_usernames=True).save()

    def test_connection(self):
        """Tests internet connection and prints out location data.

        :return: Whether a connection could be established
        :rtype: bool
        """
        self.log.info('Running proxy test.')
        fake_player = {
            Keys.NAME: 'PROXY TEST',
            Keys.UUID: ''
        }
        watcher = AdWatcher(fake_player, self.conf.load().complete_data(self.create_gameapi()))
        watcher.setup()
        changed = True
        while not watcher.does_proxy_work():
            changed = watcher.change_proxy()
            if not changed:
                break
        watcher.quit()
        self.conf.save()
        if not changed:
            self.log.error("Coundn't establish a connection.")
        return changed

    def reset_statistics(self):
        """Resets all statistics."""
        self.log.info('Resetting statistics.')
        self.conf.load().complete_data(self.create_gameapi())
        for player in self.conf[Keys.PLAYERS]:
            player[Keys.STATS] = {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}
        for proxy in self.conf[Keys.PROXIES]:
            proxy[Keys.STATS] = {Keys.FULFILLED: 0, Keys.UNFILLED: 0, Keys.LIMIT_REACHED: 0}
        self.conf.save()

    def print_statistics(self):
        """Prints statistics"""
        self.log.info('Printing statistics.')
        self.conf.load().complete_data(self.create_gameapi())
        name_len = self._print_statistic_head(
            "Players",
            "%-{}s|     F     U    F/U       M",
            (player[Keys.NAME] for player in self.conf[Keys.PLAYERS])
        )
        for player in self.conf[Keys.PLAYERS]:
            fulfilled = int(player[Keys.STATS][Keys.FULFILLED])
            unfilled = int(player[Keys.STATS][Keys.UNFILLED])
            limit_reached = int(player[Keys.STATS][Keys.LIMIT_REACHED])
            rate = 0
            if not unfilled == 0:
                rate = fulfilled / unfilled
            self.log.info("%-{}s| %5d %5d %8f %5d".format(name_len) % (
                player[Keys.NAME],
                fulfilled,
                unfilled,
                rate,
                limit_reached
            ))
        name_len = self._print_statistic_head(
            "Proxies",
            "%-{}s|     F     U    F/U       M",
            ("{}:{}".format(proxy[Keys.ADDRESS], proxy[Keys.PORT]) for proxy in self.conf[Keys.PROXIES])
        )
        for proxy in self.conf[Keys.PROXIES]:
            fulfilled = int(proxy[Keys.STATS][Keys.FULFILLED])
            unfilled = int(proxy[Keys.STATS][Keys.UNFILLED])
            limit_reached = int(proxy[Keys.STATS][Keys.LIMIT_REACHED])
            rate = 0.0
            if not unfilled == 0:
                rate = fulfilled / unfilled
            self.log.info("%-{}s| %5d %5d %8f %5d".format(name_len) % (
                "{}:{}".format(proxy[Keys.ADDRESS], proxy[Keys.PORT]),
                fulfilled,
                unfilled,
                rate,
                limit_reached
            ))

    def _print_statistic_head(self, title, header, list):
        """Prints the head of a statistic.

        :param title: Title of statistic
        :type title: str
        :param header: Header format
        :type header: str
        :param list: List of strings to determine width
        :type list: Any
        :return: Name length
        :rtype: int
        """
        name_len = max(len(str) for str in list) + 1
        width = len(header.format(name_len) % ' ')
        bar_len = int((width - len(" {} ".format(title)))/2)
        self.log.info("=" * bar_len + " {} ".format(title) + "=" * bar_len)
        self.log.info("%-{}s|     F     U    F/U       M".format(name_len) % ' ')
        return name_len



if __name__ == '__main__':
    Main().run()
