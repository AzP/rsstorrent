#!/usr/bin/env python

"""RssTorrent.py: Monitors an RSS-feed and automatically
    downloads torrents to a specified folder."""

__author__ = "Peter Asplund"
__copyright__ = "Copyright 2011"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Peter Asplund"
__email__ = "peterasplund@gentoo.se"
__status__ = "Prototype"

import os
import daemon
import feedparser
import urllib
import urllib2
import cookielib
import time
import re
import logging

feed_url = ""
login_url = ""
time_interval = 5.0
keys = []
regexp_keys = []
download_dir = ""
username = ""
password = ""
cache_file = "cache"
config_dir = "/.rsstorrent/"
config_dir_path = ""
cache_file_path = ""


def parse_config_values(valueType, values):
    """ Save config lines into variables. """
    if valueType == "login_url":
        # Save url to check
        global login_url
        login_url = values[0]
    if valueType == "rss_url":
        # Save url to check
        global feed_url
        feed_url = values[0]
    elif valueType == "interval":
        # Save time interval (in seconds) for checking feeds
        global time_interval
        time_interval = float(values[0]) #* 60.0
    elif valueType == "download_dir":
        # Save name of directory to download files to
        global download_dir
        download_dir = values[0]
    elif valueType == "keys":
        # Save list of words to look for
        global keys
        keys = values
    elif valueType == "username":
        # Save username to site
        global username
        username = values[0]
    elif valueType == "password":
        # Save password to site
        global password
        password = values[0]


def read_config_file():
    """ Open and parse the config file, save the words in a list. """
    # Open config file
    logging.info("Reading configuration file")
    with open(os.path.join(config_dir_path + "rsstorrent.conf")) as config_file:
        file_content = config_file.readlines()
        config_file.close()
        for input_line in file_content:
            # If the line is a comment, skip it
            if input_line.startswith("#"):
                continue
            # Separate line into 'setting', '=' and 'values'
            value_split = input_line.partition("=")
            # Then feed setting and values into the parser
            parse_config_values(value_split[0].strip(),
                value_split[2].strip().split())


def site_login(rss, login):
    """ Log in to url and save cookie """
    cookie_jar = cookielib.CookieJar()

    # build opener with HTTPCookieProcessor
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cookie_jar) )
    opener.addheaders.append(('User-agent',
        ('Mozilla/5.0 (X11; Linux x86_64; rv:2.0.1)'
        'Gecko/20110524 Firefox/4.0.1') ))
#    opener.addheaders.append( ('Referer',
#        'http://www.torrentbytes.net/login.php?returnto=%2F') )
    urllib2.install_opener( opener )

    # assuming the site expects 'user' and 'pass' as query params
    login_query = urllib.urlencode( { 'username': username,
        'password': password, 'login' : 'Log in!' } )

    # perform login with params
    try:
        file_handle = opener.open( login,
                            login_query )
        file_handle.close()
    except urllib2.HTTPError, exception:
        logging.error("HTTP Error:", exception.code, rss)
    except urllib2.URLError, exception:
        logging.error("URL Error:", exception.reason, rss)


def update_list_from_feed(url):
    """ Update the feed data from its url. """
    # Get feed
    feed = feedparser.parse(url)
    if feed.feed.has_key('title') == False:
        logging.error("{0} Error connecting to feed".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    else:
        logging.info("{0} Updating Feed: {1}".format(time.strftime("%Y-%m-%d %H:%M:%S"), feed['feed']['title']))

    foundItems = []
    # Loop through that list
    for key in regexp_keys:
        for item in feed["items"]:
            if key.search(item["title"]):
                logging.info(item["title"] + " : " + item["link"])
                foundItems.append(item["link"])
    return foundItems


def process_download_list(inputList):
    """ Process the list of waiting downloads. """
    # Open cache to check if file has been downloaded
    if not os.path.exists(cache_file_path):
        logging.info("Can't find cache directory")
        return

    # Open cache file and start downloading
    with open(cache_file_path, 'a+') as cache_file_handle:
        # Split the file by lines to get rid of whitespace
        cached_files = cache_file_handle.read().splitlines()
        for input_line in inputList:
            filename = input_line.partition("name=")[2]

            if filename in cached_files:
                logging.info("File already downloaded: " + input_line)
                continue

            filename = input_line.partition("name=")[2]
            logging.info("Downloading " + filename)
            try:
                request = urllib2.urlopen(input_line)
            except urllib2.HTTPError, exception:
                logging.info("HTTP Error:", exception.code, input_line)

            if request.geturl() != input_line:
                logging.info("URL Redirect - Not allowed to download")
                continue

            with open(os.path.join(download_dir, filename), 'w') as local_file:
                local_file.write(request.read())
            # Cache the downloaded file so it doesn't get downloaded again
            cache_file_handle.writelines(filename + "\n")


def convert_keys_to_regexps():
    logging.info("Searching for: ")
    logging.info(keys)
    for key in keys:
        regexp_keys.append(re.compile(key, re.IGNORECASE))


def do_main_program():
    """ Main function. """
    global config_dir
    global config_dir_path
    global cache_file_path
    global time_interval
    global regexp_keys
    home_dir = os.path.expanduser('~')
    config_dir_path = os.path.join(home_dir + config_dir)
    cache_file_path = os.path.join(config_dir_path + cache_file)
    if not os.path.exists(config_dir_path):
        os.mkdir(config_dir_path, 0o755)
        file_handle = open(cache_file_path, "w")
        file_handle.close()
        logging.info("Creating cache dir: " + cache_dir_path)

    read_config_file()

    if not os.path.exists(download_dir):
        os.mkdir(download_dir, 0o755)
    convert_keys_to_regexps()
    site_login(feed_url, login_url)

    # Main loop
    while (True):
        downloadList = update_list_from_feed(feed_url)
        process_download_list(downloadList)
        time.sleep(time_interval)

    if 0:
        logging.info("Home dir: " + home_dir)
        logging.info("Cache dir: " + cache_dir)
        logging.info("Cache dir path: " + cache_dir_path)
        logging.info("Cache file: " + cache_file)
        logging.info("Cache file path: " + cache_file_path)
        logging.info(feed_url)
        logging.info(login_url)
        logging.info(keys)
        logging.info(download_dir)

if __name__ == "__main__":
    do_main_program()

#with daemon.DaemonContext():
#    do_main_program()

