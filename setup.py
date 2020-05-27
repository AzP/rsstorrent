#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Setup for rsstorrent."""

from setuptools import setup
from rsstorrent import __version__

with open("README.md") as readme:
    setup(
        name="rsstorrent",
        version=__version__,
        description="Monitors an RSS-feed and automatically "
        "downloads torrents to a specified folder.",
        long_description=readme.read(),
        license="GPL-3",
        author="Peter Asplund",
        author_email="peterasplund@gentoo.se",
        url="https://github.com/AzP/rsstorrent",
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "Intended Audience :: End Users/Desktop",
            "License :: OSI Approved :: GPL-3 License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
        ],
        py_modules=["rsstorrent"],
        keywords="automation, p2p, network",
        install_requires=["python-daemon", "feedparser"],
        entry_points={"console_scripts": ["rsstorrent = rsstorrent:do_main_program"]},
    )
