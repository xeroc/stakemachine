#!/usr/bin/env python

from setuptools import setup, find_packages

VERSION = '0.0.6'

setup(
    name='dexbot',
    version=VERSION,
    description='Trading bot for the DEX (BitShares)',
    long_description=open('README.md').read(),
    author='Codaone Oy',
    author_email='support@codaone.com',
    maintainer='Codaone Oy',
    maintainer_email='support@codaone.com',
    url='http://www.github.com/codaone/dexbot',
    keywords=['DEX', 'bot', 'trading', 'api', 'blockchain'],
    packages=[
        "dexbot",
        "dexbot.strategies",
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
    ],
    entry_points={
        'console_scripts': [
            'dexbot = dexbot.cli:main',
        ],
    },
    install_requires=[
        "bitshares==0.1.11.beta",
        "uptick>=0.1.4",
        "prettytable",
        "click",
        "click-datetime",
        "colorama",
        "tqdm",
        "pyyaml",
        "sqlalchemy",
        "appdirs",
        "pyqt5",
        "ruamel.yaml"
    ],
    dependency_links=[
        # Temporally force downloads from a different repo, change this once the websocket fix has been merged
        "https://github.com/mikakoi/python-bitshares/tarball/websocket-fix#egg=bitshares-0.1.11.beta"
    ],
    include_package_data=True,
)
