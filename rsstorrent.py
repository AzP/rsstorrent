#!/usr/bin/env python

"""RssTorrent.py: Monitors an RSS-feed and automatically
    downloads torrents to a specified folder."""

__author__ = "Peter Asplund"
__copyright__ = "Copyleft 2011"
__credits__ = ["ikkemaniac"]
__license__ = "GPL"
__version__ = "0.4"
__maintainer__ = "Peter Asplund"
__email__ = "peterasplund@gentoo.se"
__status__ = "Beta"

import os
import daemon
import signal
import lockfile
import feedparser
import urllib
import urllib2
import cookielib
import time
import re
import logging
import ConfigParser
from optparse import OptionParser

RUNNING = True


class Child:
    """ Child process """
    child_id = ""
    pid = ""
    is_alive = False

    def __init__(self, child_id):
        logging.debug("Created child number:" + str(child_id))
        self.child_id = child_id
        self.is_alive = True

    def print_debug(self):
        """ Dump all local variables """
        logging.debug("Child:" + self.child_id)
        logging.debug("Pid:" + self.pid)
        logging.debug("Is Alive: " + self.is_alive)


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

    def __init__(self):
        return

    def print_debug(self):
        """ Dump all local variables """
        logging.debug("Site: ")
        logging.debug("Feed url: " + self.feed_url)
        logging.debug("Login url: " + self.login_url)
        logging.debug("Keys: " + str(self.keys))
        logging.debug("Interval (in seconds): " + str(self.time_interval))
        logging.debug("---------------------")


def create_config_file(cfg_file):
    "("" Generate an empty config file """
    with open(cfg_file, 'w+') as cfg_file_handle:
        # Split the file by lines to get rid of whitespace
        lines = ["[General]\n",
            "# Directory which to download torrents to\n",
            "download_dir = /home/username/Downloads/\n",
            "\n",
            "[Site1]\n",
            "# Interval between checks in minutes\n",
            "interval = 30\n",
            "\n",
            "# URL to rss feed\n",
            "rss_url = http://www.urltosite.com\n",
            "\n",
            "# URL to site login page/script\n",
            "login_url = http://www.urltosite.com/takelogin.php\n",
            "\n",
            "# Search keys for the parsing\n",
            "keys = keys*to*search*for separated*by spaces\n",
            "\n",
            "# Username and Password to torrent site\n",
            "username = username\n",
            "password = password\n"]
        for line in lines:
            cfg_file_handle.writelines(line)


def read_config_file(cfg_file, sites, env):
    """ Open and parse the config file, save the words in a list. """
    # Open config file
    logging.info("Reading configuration file: " + cfg_file)
    config = ConfigParser.SafeConfigParser()
    config.read(cfg_file)
    sections = config.sections()
    for section in sections:
        site = Site()
        if section == "General":
            # Save name of directory to download files to
            env.download_dir = config.get(section, "download_dir")
        else:
            # Save url to check
            site.login_url = config.get(section, "login_url")
            # Save url to check
            site.feed_url = config.get(section, "rss_url")
            # Save time interval (in seconds) for checking feeds
            site.time_interval = config.getfloat(section, "interval") * 60.0
            # Save list of words to look for
            keys_str = str(config.get(section, "keys"))
            site.keys = keys_str.split()
            # Save username to site
            site.username = config.get(section, "username")
            # Save password to site
            site.password = config.get(section, "password")
            # Add to array of sites
            sites.append(site)
    # safety check
    if len(sites) < 1:
        logging.critical("Can't read config file")
        exit(-1)


def site_login(site):
    """ Log in to url and save cookie """
    cookie_jar = cookielib.CookieJar()

    # build opener with HTTPCookieProcessor
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    opener.addheaders.append(('User-agent',
        ('Mozilla/5.0 (X11; Linux x86_64; rv:2.0.1)'
        'Gecko/20110524 Firefox/4.0.1')))
    urllib2.install_opener(opener)

    # assuming the site expects 'user' and 'pass' as query params
    login_query = urllib.urlencode({'username': site.username,
        'password': site.password, 'login': 'Log in!'})

    # perform login with params
    try:
        file_handle = opener.open(site.login_url,
                            login_query)
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
                logging.debug("Found match: " + item["title"] + " : " + item["link"])
                found_items.append(item["title"] : item["link"])
    logging.debug("Updated Feed: " + feed['feed']['title'])
    return found_items


def process_download_list(cache, download_dir, input_list, options):
    """ Process the list of waiting downloads. """
    # Open cache to check if file has been downloaded
    if not os.path.exists(cache):
        if not options.cache_ignore:
            logging.error("Can't find cache directory")
            return
        else:
            logging.debug(
            "No cache file was found, but caching was ignored anyway"
            )

    # Open cache file and start downloading
    with open(cache, 'a+') as cache_file_handle:
        # Split the file by lines to get rid of whitespace
        cached_files = cache_file_handle.read().splitlines()
        for title in input_list["title"]:
            # For what site?
            # Index -1 returns last position
            #filename = input_line.split("/")[-1]
            # For torrentbytes
            #filename = input_line.partition("name=")[2]
            filename = title + ".torrent"
            http_url = input_list[title]
            logging.debug("Processing: " + http_url)
            logging.debug("Filename resolved to: " + filename)
            if len(filename) < 1:
                logging.critical("I was not able to find you a filename!\
                The file cannot be saved!")
                continue

            if (filename in cached_files) and not options.cache_ignore:
                logging.debug("File already downloaded: " + input_line)
                continue
            if options.no_downloads:
                continue

            logging.info("Start downloading: " + filename)
            try:
                request = urllib2.urlopen(http_url)
            except urllib2.HTTPError, exception:
                msg = "HTTP Error: " + exception.code + " Line:" + http_url
                logging.info(msg)

            if request.geturl() != http_url:
                logging.info("URL Redirect - Not allowed to download")
                continue

            with open(os.path.join(download_dir, filename), 'w') as local_file:
                local_file.write(request.read())

            # Cache the downloaded file so it doesn't get downloaded again
            cache_file_handle.writelines(filename + "\n")


def convert_keys_to_regexps(sites):
    """ Process the list of keys and convert
        to compiled regular expressions. """
    for site in sites:
        for key in site.keys:
            site.regexp_keys.append(re.compile(key, re.IGNORECASE))


def setup_logging(env, options):
    """ Setup logging to file or tty. """
    log_file = ''
    # Logging format for logfile and console messages
    formatting = '%(asctime)s (%(process)d) %(levelname)s: %(message)s'

    # set log filepath
    if options.log_file:
        log_file = options.log_file
    else:
        log_file = os.path.join(env.config_dir_path + "rsstorrent.log")

    # IMPORTANT!
    # It is important to define the basic file
    # logging before the console logging
    if options.debug:
        logging.basicConfig(filename=log_file, format=formatting,
                level=logging.DEBUG)
    elif options.verbose:
        logging.basicConfig(filename=log_file, format=formatting,
                level=logging.INFO)
    else:
        logging.basicConfig(filename=log_file, format=formatting,
                level=logging.CRITICAL)

    # Always print messages to the console
    # In normal operating mode only CRITICAL messages will be displayed
    console = logging.StreamHandler()
    if options.debug:
        # define a Handler which writes CRITICAL messages to the sys.stderr
        console.setLevel(logging.DEBUG)
    elif options.verbose:
        console.setLevel(logging.INFO)
    else:
        console.setLevel(logging.CRITICAL)

    console.setFormatter(logging.Formatter(formatting))
    logging.getLogger('').addHandler(console)

    return log_file


def cleanup_program():
    """ Set RUNNING to false so program loop exits. """
    global RUNNING
    RUNNING = False
    logging.info("RUNNING set to False")


def parse_cmd_arguments():
    """ Parse command line arguments """
    # Parse command line commands
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
            help="Verbose logging", default=False)
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
            help="Print debug information to console", default=False)
    parser.add_option("-D", "--daemon", action="store_true", dest="daemon",
            help="Run as daemon", default=False)
    parser.add_option("-x", "--stop", action="store_true", dest="stop",
            help="Stop running daemon (does not work currently)",
            default=False)
    parser.add_option("-l", "--logfile", dest="log_file",
            help="Write log to FILE", metavar="FILE")
    parser.add_option("-p", "--pidfile", dest="pid_file",
            help="Set pidfile to FILE", metavar="FILE",
            default='/var/run/rsstorrent/rsstorrent.pid')
    parser.add_option("--cc", "--cache-clear", action="store_true",
            dest="cache_clear", help="Clear the cache file", default=False)
    parser.add_option("--ci", "--cache-ignore", action="store_true",
            dest="cache_ignore",
            help="Ignore the cache and download all files again",
            default=False)
    parser.add_option("--nd", "--no-downloads", action="store_true",
            dest="no_downloads",
            help="Don't actually download the files", default=False)
    (options, args) = parser.parse_args()

    if args:
        print("Required variables not supplied.")
        exit(-1)

    return options


def check_output_files(env, options):
    """ Check sanity of output directory and handle cache cleans """
    if options.cache_clear:
        # clear cache file
        open(env.cache_file_path, 'w').close()
        logging.info("Cleared cache")
        exit(0)
    if not os.path.exists(env.download_dir):
        os.mkdir(env.download_dir, 0o755)


def do_main_program():
    """ Main function. """
    options = parse_cmd_arguments()
    env = Environment()
    log_file_path = setup_logging(env, options)

    logging.info("Starting rsstorrent...")

    # Read config file, if it can't find it, create it
    if not os.path.exists(env.config_file_path):
        create_config_file(env.config_dir_path + env.config_file)
        logging.warning("There was no config file found, I just created one.")
        logging.critical("Please check " + env.config_dir_path +
                env.config_file + " before restarting!")
        exit(-1)

    sites = []
    read_config_file(env.config_file_path, sites, env)
    check_output_files(env, options)
    convert_keys_to_regexps(sites)
    for site in sites:
        site_login(site)

    # Print verbose/debug output if enabled
    if options.verbose:
        env.print_debug()
        logging.info("Ignore cache: " + str(bool(options.cache_ignore)))
        for site in sites:
            site.print_debug()

    # Start the program (either in or without daemon mode)
    if options.daemon:
        context = initiate_daemon(options, env, log_file_path)
        logging.debug("Entering daemon context")
        with context:
            logging.debug("Entered daemon context")
            main_loop(env, sites, options)
        logging.debug("Exited daemon context")
    else:
        main_loop(env, sites, options)
    logging.info("Stopping rsstorrent...")
    logging.info("Exting.")


def initiate_daemon(options, env, log_file_path, logging):
    """ Set up daemon context and return it """
    # Set up some Daemon stuff
    context = daemon.DaemonContext(
            umask=0o002,
            pidfile=lockfile.FileLock(options.pid_file),
            )
    context.signal_map = {
            signal.SIGTERM: cleanup_program,
            signal.SIGHUP: 'terminate',
            }

    if options.stop:
        logging.info("Caught stop signal")
        logging.info("Context started: " + str(context.is_open))
        if context.is_open:
            context.close()
        else:
            logging.info("No context with that pid open")
        exit(0)

    # Check if the daemon is already running
    # or at least if it has left a pid file behind
    try:
        open(options.pid_file + '.lock', 'r')
        logging.info("pid-file exists, exiting")
        exit(-1)
    except IOError:
        pass

    # Open all important files and list them
    cache_file_handle = open(env.cache_file_path, 'a+')
    config_file_handle = open(env.config_file_path, 'a+')
    if log_file_path:
        log_file_handle = logging.root.handlers[0].stream.fileno()
        logging.debug("Adding logging handle to files_preserve: "
                + log_file_path)
        context.files_preserve = [cache_file_handle,
                config_file_handle,
                log_file_handle]
    else:
        context.files_preserve = [cache_file_handle, config_file_handle]
    return context


def main_loop(env, sites, options):
    """ Main program loop """
    global RUNNING
    RUNNING = True
    children = []
    num_children = 0
    # Main loop
    for site in sites:
        num_children += 1
        child = os.fork()
        logging.debug("Working: " + site.feed_url)
        if child:
            # still in the parent process
            logging.debug("Create child proces for: " + site.feed_url)
            ctmp = Child(num_children)
            ctmp.pid = child
            children.append(ctmp)
        else:
            while(RUNNING):
                # in child process
                download_list = update_list_from_feed(site.feed_url,
                        site.regexp_keys)
                if len(download_list):
                    logging.debug("Start downloading, I found " +
                            str(len(download_list)) + " items.")
                    process_download_list(env.cache_file_path,
                            env.download_dir, download_list, options)
                time.sleep(site.time_interval)
            exit(0)

    while(RUNNING):
        logging.debug("Looking into children...")
        for child in children:
            (pid, status) = os.waitpid(child.pid, os.WNOHANG)
            if pid < 0:
                child.is_alive = False
                break
        time.sleep(60)


try:
    if __name__ == "__main__":
        do_main_program()

# catch keyboard exception
except KeyboardInterrupt:
    logging.critical("\n")
    logging.critical("Keyboard Interrupted!")
