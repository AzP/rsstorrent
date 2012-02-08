#!/usr/bin/env python

"""RssTorrent.py: Monitors an RSS-feed and automatically
    downloads torrents to a specified folder."""

__author__ = "Peter Asplund"
__copyright__ = "Copyleft 2011"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "0.3"
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
import shutil
import ConfigParser
from optparse import OptionParser

global Running;
global children;

class Child:

    pid = ""
    isAlive = False

    def __init__(self):
        self.isAlive = True

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
        logging.debug("Site: ")
        logging.debug(self.feed_url)
        logging.debug(self.login_url)
        logging.debug(self.keys)
	# spacer for easy reading
	logging.debug(".")

def create_config_file(cfg_file):
    with open(cfg_file, 'w+') as cfg_file_handle:
        # Split the file by lines to get rid of whitespace
	lines = ["[General]\n", "# Directory which to download torrents to\n", "download_dir = /home/username/Downloads/\n", "\n", "[Site1]\n", "# Interval between checks in minutes\n", "interval = 7\n", "\n", "# URL to rss feed\n", "rss_url = http://www.urltosite.com\n", "\n", "# URL to site login page/script\n", "login_url = http://www.urltosite.com/takelogin.php\n", "\n", "# Search keys for the parsing\n", "keys = keys*to*search*for separated*by spaces\n", "\n", "# Username and Password to torrent site\n", "username = username\n", "password = password\n"]
        for line in lines:
            cfg_file_handle.writelines(line)

def read_config_file(cfg_file, sites, env):
    """ Open and parse the config file, save the words in a list. """
    # Open config file
    logging.info("Reading configuration file: " + cfg_file)
    config = ConfigParser.SafeConfigParser()
    config.read(cfg_file)
    sections = config.sections()
    site = Site()
    for section in sections:
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
        return False

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
    logging.info("Updated Feed: " + feed['feed']['title'])
    return found_items


def process_download_list(cache, download_dir, input_list, cache_ign):
    """ Process the list of waiting downloads. """
    # Open cache to check if file has been downloaded
    if not os.path.exists(cache):
        logging.info("Can't find cache directory")
        return

    # Open cache file and start downloading
    with open(cache, 'a+') as cache_file_handle:
        global no_downloads
        # Split the file by lines to get rid of whitespace
        cached_files = cache_file_handle.read().splitlines()
        for input_line in input_list:
            filename = input_line.split("/")[-1]
            logging.info("Processing: " + input_line)

            if len(filename) < 1:
                logging.critical("I was not able to find you a filename! The file cannot be saved!")
                continue

            logging.info("Ignore cache: " + str(bool(cache_ign)))

            if (filename in cached_files) and not cache_ign:
                logging.info("File already downloaded: " + input_line)
                continue
            #filename = input_line.partition("name=")[2]
            logging.info("Downloading: " + filename)
            if no_downloads:
                continue

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


def convert_keys_to_regexps(sites):
    """ Process the list of keys and convert
        to compiled regular expressions. """
    for site in sites:
        logging.info("Searching for: " + str(site.keys))
        for key in site.keys:
            logging.info("Key: " + key)
            site.regexp_keys.append(re.compile(key, re.IGNORECASE))


def setup_logging(env, options):
    """ Setup logging to file or tty. """
    log_file=''
    formatting = '%(asctime)s (%(process)d) %(levelname)s: %(message)s'

    if not options.debug:
        if options.log_file:
            log_file = options.log_file
        else:
            log_file = os.path.join(env.config_dir_path + "rsstorrent.log")
        # define a Handler which writes CRITICAL messages to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.CRITICAL)
        console.setFormatter(logging.Formatter(formatting))
        logging.getLogger('').addHandler(console)

    if (options.verbose):
        logging.basicConfig(filename=log_file, format=formatting, level=logging.DEBUG)
    else:
        logging.basicConfig(filename=log_file, format=formatting, level=logging.INFO)
    return log_file


def cleanup_program():
    """ Set Running to false so program loop exits. """
    global Running;
    Running=False;
    logging.info("Running set to False")


def do_main_program():
    """ Main function. """
    # Parse command line commands
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                    help="Verbose logging", default=False)
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                    help="Print debug information to console", default=False)
    parser.add_option("-D", "--daemon", action="store_true", dest="daemon",
                    help="Run as daemon", default=False)
    parser.add_option("-l", "--logfile", dest="log_file",
                    help="write log to FILE", metavar="FILE")
    parser.add_option("-p", "--pidfile", dest="pid_file",
                    help="set pidfile to FILE", metavar="FILE",
                    default='/var/run/rsstorrent/rsstorrent.pid')
    parser.add_option("--cc", "--cache-clear", action="store_true", dest="cache_clear",
                    help="clear the cache file", default=False)
    parser.add_option("--ci", "--cache-ignore", action="store_true", dest="cache_ignore",
                    help="work the cache just as normal, except download all files anyway", default=False)
    parser.add_option("--nd", "--no-downloads", action="store_true", dest="no_downloads",
                    help="perform a dry run, iaw: don't actually download the files", default=False)
    (options, args) = parser.parse_args()

    if args:
        logging.warning("Required variables not supplied")

    env = Environment()
    log_file_path = setup_logging(env, options)

    # Read config file, if it can't find it, create one
    if not os.path.exists(env.config_file_path):
	create_config_file(env.config_dir_path + env.config_file)
	logging.critical("There was no config file found, I just created one.")
	logging.critical("Please check " + env.config_dir_path + env.config_file + " before restarting!")
	exit(-1)

    #sites = Site()
    sites = []
    config_success = read_config_file(env.config_file_path,
                                    sites, env)
    if not config_success:
        logging.critical("Can't read config file")
        exit(-1)

    if options.cache_clear:
	# clear cache file
	open(env.cache_file_path, 'w').close()
	exit(0)

    if not os.path.exists(env.download_dir):
        os.mkdir(env.download_dir, 0o755)
    convert_keys_to_regexps(sites)
    site_login(sites)

    # Print verbose/debug output if enabled
    if options.verbose:
        env.print_debug()
        for site in sites:
            site.print_debug()

    
    if options.daemon:
        # Set up some Daemon stuff
        context = daemon.DaemonContext(
                umask=0o002,
                pidfile=lockfile.FileLock(options.pid_file),
                )
        context.signal_map = {
                signal.SIGTERM: cleanup_program,
                signal.SIGHUP: 'terminate',
                }
        # Open all important files and list them
        cache_file_handle = open(env.cache_file_path, 'a+') 
        config_file_handle = open(env.config_file_path, 'a+') 
        if log_file_path:
            log_file_handle = open(log_file_path, 'w+') 
            context.file_preserve = [cache_file_handle, config_file_handle,
                    log_file_handle]
        else:
            context.file_preserve = [cache_file_handle, config_file_handle]

        with context:
            logging.info("Entering daemon context")
            main_loop(env, sites, options)
    else:
        main_loop(env, sites, options)

def main_loop(env, sites, options):
    """ Main program loop """
    global Running;
    Running = True;
    global children;
    children = []
    # Main loop
    # while (Running):
    for site in sites:
        child = os.fork()
        if child:
            # still in the parent process
            # while(Running):
            logging.debug("---- in here " + site.feed_url)
            ctmp = Child()
            ctmp.pid = child
            children.append(ctmp)
        else:
            while(Running):
                """# in child process
                download_list = update_list_from_feed(site.feed_url, site.regexp_keys)
                if len(download_list):
                    logging.debug("Start downloading, I found " + len(download_list) + " items.")
                    process_download_list(env.cache_file_path,
                            env.download_dir, download_list, options.cache_ignore)
                time.sleep(site.time_interval)"""
                logging.debug("lala: " + site.feed_url)
                time.sleep(5)
                logging.debug("lala end: " + site.feed_url)
                exit(0)
        logging.debug(site.feed_url)
    #exit(0)
    #while(Running):
    for child in children:
        while(child.isAlive):
            logging.debug("in here")
            #child._exit(9)
            (pid, status) = os.waitpid(child.pid, os.WNOHANG)
            if pid <= 0:
                break
            child.isAlive = False
    time.sleep(10)


try:
    if __name__ == "__main__":
        do_main_program()

# catch keyboard exception
except KeyboardInterrupt:
    #for child in children:
        #child._exit(9)
    #    (pid, status) = os.waitpid(-1, os.WNOHANG)
    #    if pid <= 0:
    #        break

    logging.critical("\n")
    logging.critical("Keyboard Interrupted!")

