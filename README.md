# Rsstorrent

Rsstorrent.py: A small tool that monitors an RSS-feed and automatically downloads torrents to a specified folder.

It daemonizes after start and polls specified URLs at a specified interval. Init files are included for Gentoo (rc-init) and Debian/Ubuntu (not systemd).

## Dependencies

It utilizes various packages to work. Dependencies:

    # Standard packages
    os
    signal
    urllib.request
    urllib.parse
    urllib.error
    http.cookiejar
    time
    re
    logging
    configparser
    argparse
    # Special packages
    feedparser
    daemon


## Instructions for use

1. Download the files and unpack into a directory.
2. Change the file `rsstorrent.py` to be runnable (`chmod +x rsstorrent.py` or right-click it, choose properties and fix it there).

    2.1. Copy the rsstorrent.py to `/usr/bin` or `/usr/local/bin` to make it launchable via init script.

3. Copy the config file to `~/.rsstorrents/` and edit it there. The comments in the file should be fairly self-explanatory (if not, please file a bug!):

    3.1. Set an RSS-feed to monitor. This might include your login and some hash-values generated by your site.

    3.2. Set the directory to which you want to download your files.

    3.3. Add search patterns in a basic regular expression form. ".*" (without the quotes) is the wildcard to use. "." means any character and "*" means 0 or more occurrences of it. Rsstorrent using Python's regular expressions without manipulation.

    3.4. Set your username and password to the torrent site, this is used to download the actual files.

4. Copy the init file that suits your system (Gentoo or Debian/Ubuntu. Feel free to contribute with more init files!) to the `/etc/init.d/` folder and remove the trailing distribution name. Make it executable by doing `chmod -x rsstorrent`.
5. Then start the script by running `/etc/init.d/rsstorrent start`.

and after that you should be up'n'running. Over and out!
