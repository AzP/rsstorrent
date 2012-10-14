#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Setup for rsstorrent."""

from setuptools import setup

def version():
    """Return version string."""
    with open('rsstorrent.py') as input_file:
        for line in input_file:
            if line.startswith('__version__'):
                import ast
                return ast.literal_eval(line.split('=')[1].strip())


with open('README.md') as readme:
    setup(
        name='rsstorrent',
        version=version(),
        description="""Monitors an RSS-feed and automatically
                       downloads torrents to a specified folder."""
        long_description=readme.read(),
        license='GPL-3',
        author='Peter Asplund',
        author_email='peterasplund@gentoo.se',
        url='https://github.com/AzP/rsstorrent',
        classifiers=[
            'Development Status :: 5 - Stable',
            'Environment :: Console',
            'Intended Audience :: Users',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Unix Shell',
        ],
        keywords='automation, p2p, network',
        install_requires=['daemon', 'feedparser'],
        entry_points={'console_scripts': ['rsstorrent = rsstorrent:main']},
    )
