#!/usr/bin/env python

"""RssTorrent.py: Monitors an RSS-feed and automatically
    downloads torrents to a specified folder."""

__author__ = "Peter Asplund"
__copyright__ = "Copyright 2011"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "0.2"
__maintainer__ = "Peter Asplund"
__email__ = "peterasplund@gentoo.se"
__status__ = "Beta"

import os
import daemon
import feedparser
import urllib
import urllib2
import cookielib
import time
import re
import logging
import shutil
import ConfigParser
from optparse import OptionParser


class Environment:
    """ Keeps track of all files and directories """
    # File names
    cache_file = "cache"
    config_file = "rsstorrent.conf"

    # Directory names
    home_dir = ""
    config_dir = "/.rsstorrent/"
    download_dir = ""

    # Full paths
    cache_dir_path = ""
    cache_file_path = ""
    config_file_path = ""
    config_dir_path = ""

    def __init__(self):
        self.home_dir = os.path.expanduser('~')
        self.cache_dir_path = os.path.join(self.home_dir + self.config_dir)
        self.config_dir_path = os.path.join(self.home_dir + self.config_dir)
        self.cache_file_path = os.path.join(self.config_dir_path +
                                            self.cache_file)
        self.config_file_path = os.path.join(self.config_dir_path +
                                            self.config_file)
        self.download_dir = os.path.join(self.home_dir + "/Download")
        if not os.path.exists(self.config_dir_path):
            os.mkdir(self.config_dir_path, 0o755)
            file_handle = open(self.cache_file_path, "w")
            file_handle.close()

    def print_debug(self):
        """ Dump all local variables """
        logging.debug("Home dir: " + self.home_dir)
        logging.debug("Cache dir path: " + self.cache_dir_path)
        logging.debug("Cache file: " + self.cache_file)
        logging.debug("Cache file path: " + self.cache_file_path)
        logging.debug("Download dir path: " + self.download_dir)

class Site:
    """ Represents a monitored site """
    feed_url = ""
    login_url = ""
    time_interval = 5.0
    keys = []
    regexp_keys = []
    username = ""
    password = ""

    def print_debug(self):
        """ Dump all local variables """
        logging.debug("\nSite: ")
        logging.debug(self.feed_url)
        logging.debug(self.login_url)
        logging.debug(self.keys)


def read_config_file(cfg_file, sites, download_dir):
    """ Open and parse the config file, save the words in a list. """
    # Open config file
    logging.info("Reading configuration file")
    config = ConfigParser.SafeConfigParser()
    config.read(cfg_file)
    sections = config.sections()
    for section in sections:
		if section == "General":
			# Save name of directory to download files to
		    download_dir = config.get(section, "download_dir")
		else:
			# Save url to check
			sites.login_url = config.get(section, "login_url")
			# Save url to check
			sites.feed_url = config.get(section, "rss_url")
			# Save time interval (in seconds) for checking feeds
			sites.time_interval = config.getfloat(section, "interval") * 60.0
			# Save list of words to look for
			keys_str = config.get(section, "keys")
			sites.keys = keys_str.split()
			# Save username to site
			sites.username = config.get(section, "username")
			# Save password to site
			sites.password = config.get(section, "password")
    return True


def site_login(site):
    """ Log in to url and save cookie """
    cookie_jar = cookielib.CookieJar()

    # build opener with HTTPCookieProcessor
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cookie_jar) )
    opener.addheaders.append(('User-agent',
        ('Mozilla/5.0 (X11; Linux x86_64; rv:2.0.1)'
        'Gecko/20110524 Firefox/4.0.1') ))
    urllib2.install_opener( opener )

    # assuming the site expects 'user' and 'pass' as query params
    login_query = urllib.urlencode( { 'username': site.username,
        'password': site.password, 'login' : 'Log in!' } )

    # perform login with params
    try:
        file_handle = opener.open( site.login_url,
                            login_query )
        file_handle.close()
    except urllib2.HTTPError, exception:
        logging.error("HTTP Error: " + exception.code +
                " Site:" + site.feed_url)
    except urllib2.URLError, exception:
        logging.error("URL Error: " + exception.reason +
                " Site:" + site.feed_url)


def update_list_from_feed(url, regexp_keys):
    """ Update the feed data from its url. """
    found_items = []

    # Get feed
    feed = feedparser.parse(url)
    if 'title' not in feed.feed:
        logging.error("Error connecting to feed")
        return found_items
    else:
        logging.info("Updating Feed: " + feed['feed']['title'])

    # Loop through that list
    for key in regexp_keys:
        for item in feed["items"]:
            if key.search(item["title"]):
                logging.info(item["title"] + " : " + item["link"])
                found_items.append(item["link"])
    return found_items


def process_download_list(cache, download_dir, input_list):
    """ Process the list of waiting downloads. """
    # Open cache to check if file has been downloaded
    if not os.path.exists(cache):
        logging.info("Can't find cache directory")
        return

    # Open cache file and start downloading
    with open(cache, 'a+') as cache_file_handle:
        # Split the file by lines to get rid of whitespace
        cached_files = cache_file_handle.read().splitlines()
        for input_line in input_list:
            filename = input_line.partition("name=")[2]

            if filename in cached_files:
                logging.info("File already downloaded: " + input_line)
                continue

            filename = input_line.partition("name=")[2]
            logging.info("Downloading " + filename)
            try:
                request = urllib2.urlopen(input_line)
            except urllib2.HTTPError, exception:
                msg = "HTTP Error: " + exception.code + " Line:" + input_line
                logging.info(msg)

            if request.geturl() != input_line:
                logging.info("URL Redirect - Not allowed to download")
                continue

            with open(os.path.join(download_dir, filename), 'w') as local_file:
                local_file.write(request.read())
            # Cache the downloaded file so it doesn't get downloaded again
            cache_file_handle.writelines(filename + "\n")


def convert_keys_to_regexps(site):
    """ Process the list of keys and convert
        to compiled regular expressions. """
    logging.info("Searching for: ")
    logging.info(site.keys)
    for key in site.keys:
        site.regexp_keys.append(re.compile(key, re.IGNORECASE))


def do_main_program():
    """ Main function. """
    # Parse command line commands
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                    help="Print debug information to console", default=False)
    parser.add_option("-l", "--logfile", dest="log_file",
                    help="write log to FILE", metavar="FILE")
    (options, args) = parser.parse_args()

    if args:
        logging.warning("Required variables not supplied")

    env = Environment()

    # Setup logging to file
    if options.log_file:
        log_file = options.log_file
    else:
        log_file = os.path.join(env.config_dir_path + "rsstorrent.log")

    formatting = '%(asctime)s %(levelname)s: %(message)s'
    if (options.verbose):
        print("Verbose mode")
        logging.basicConfig(format=formatting, level=logging.DEBUG)
    else:
        logging.basicConfig(filename=log_file,
                format=formatting,
                level=logging.DEBUG)

    # Read config file, if it can't find it, copy it from current folder
    if not os.path.exists(env.config_file_path):
        shutil.copy("rsstorrent.conf", env.config_dir_path)

    sites = Site()
    config_success = read_config_file(env.config_file_path,
                                    sites, env.download_dir)
    if not config_success:
        logging.critical("Can't read config file")
        exit(-1)

    if not os.path.exists(env.download_dir):
        os.mkdir(env.download_dir, 0o755)
    convert_keys_to_regexps(sites)
    site_login(sites)

    # Main loop
    while (True):
        download_list = update_list_from_feed(sites.feed_url, sites.regexp_keys)

        if len(download_list):
            process_download_list(env.cache_file_path,
                    env.download_dir, download_list)

        time.sleep(sites.time_interval)

    if 0:
        env.print_debug()
        for site in sites:
            site.print_debug()

if __name__ == "__main__":
    do_main_program()

with daemon.DaemonContext():
    do_main_program()

