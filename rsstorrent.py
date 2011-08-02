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
import feedparser
import urllib
import urllib2
import cookielib
import time
import re

feed_url = ""
time_interval = 5.0
keys = []
regexp_keys = []
download_dir = ""
username = ""
password = ""
cache_file = "cache"
cache_dir = "/.rsstorrent/"
cache_dir_path = ""
cache_file_path = ""


def parse_config_values(valueType, values):
    """ Save config lines into variables. """
    if valueType == "url":
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
    with open("./rsstorrent.conf") as config_file:
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


def site_login(url):
    """ Log in to url and save cookie """
    cookie_jar = cookielib.CookieJar()

    # build opener with HTTPCookieProcessor
    opener = urllib2.build_opener( urllib2.HTTPCookieProcessor(cookie_jar) )
    opener.addheaders.append(('User-agent',
        ('Mozilla/5.0 (X11; Linux x86_64; rv:2.0.1)'
        'Gecko/20110524 Firefox/4.0.1') ))
    opener.addheaders.append( ('Referer',
        'http://www.torrentbytes.net/login.php?returnto=%2F') )
    urllib2.install_opener( opener )

    # assuming the site expects 'user' and 'pass' as query params
    login_query = urllib.urlencode( { 'username': username,
        'password': password, 'login' : 'Log in!' } )

    # perform login with params
    try:
        file_handle = opener.open( 'http://www.torrentbytes.net/takelogin.php',
                            login_query )
        file_handle.close()
    except urllib2.HTTPError, exception:
        print "HTTP Error:", exception.code, url
    except urllib2.URLError, exception:
        print "URL Error:", exception.reason, url


def update_list_from_feed(url):
    """ Update the feed data from its url. """
    # Get feed
    feed = feedparser.parse(url)
    if feed.has_key('feed') == False:
        print("{0} Error connecting to feed".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    else:
        print("{0} Updating Feed: {1}".format(time.strftime("%Y-%m-%d %H:%M:%S"), feed['feed'].title))

    foundItems = []
    # Loop through that list
    for key in regexp_keys:
        for item in feed["items"]:
            # if key.lower() in item["title"].lower():
            if key.search(item["title"]):
                print(item["title"] + " : " + item["link"])
                foundItems.append(item["link"])
    return foundItems


def process_download_list(inputList):
    """ Process the list of waiting downloads. """
    # Open cache to check if file has been downloaded
    if not os.path.exists(cache_dir_path):
        print("Can't find cache directory")
        return

    # Open cache file and start downloading
    with open(cache_file_path, 'a+') as cache_file_handle:
        # Split the file by lines to get rid of whitespace
        cached_files = cache_file_handle.read().splitlines()
        for input_line in inputList:
            filename = input_line.partition("name=")[2]

            if filename in cached_files:
                print("File already downloaded: " + input_line)
                continue

            filename = input_line.partition("name=")[2]
            print("Downloading " + filename)
            try:
                request = urllib2.urlopen(input_line)
            except urllib2.HTTPError, exception:
                print("HTTP Error:", exception.code, input_line)

            if request.geturl() != input_line:
                print("URL Redirect - Not allowed to download")
                continue

            with open(os.path.join(download_dir, filename), 'w') as local_file:
                local_file.write(request.read())
            # Cache the downloaded file so it doesn't get downloaded again
            cache_file_handle.writelines(filename + "\n")


def convert_keys_to_regexps():
    print(keys)
    for key in keys:
        regexp_keys.append(re.compile(key, re.IGNORECASE))
    print(regexp_keys)


def main():
    """ Main function. """
    global cache_dir_path
    global cache_file_path
    global time_interval
    global regexp_keys
    home_dir = os.path.expanduser('~')
    cache_dir_path = os.path.join(home_dir + cache_dir)
    cache_file_path = os.path.join(cache_dir_path + cache_file)
    if not os.path.exists(cache_dir_path):
        os.mkdir(cache_dir_path, 0o755)
        file_handle = open(cache_file_path, "w")
        file_handle.close()
        print("Creating cache dir: " + cache_dir_path)

    read_config_file()

    if not os.path.exists(download_dir):
        os.mkdir(download_dir, 0o755)
    convert_keys_to_regexps()
    site_login(feed_url)

    # Main loop
    #while (True):
    downloadList = update_list_from_feed(feed_url)
    process_download_list(downloadList)
    time.sleep(time_interval)

    if 0:
        print("Home dir: " + home_dir)
        print("Cache dir: " + cache_dir)
        print("Cache dir path: " + cache_dir_path)
        print("Cache file: " + cache_file)
        print("Cache file path: " + cache_file_path)
        print(feed_url)
        print(keys)
        print(download_dir)


if __name__ == "__main__":
    main()
