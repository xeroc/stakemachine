#!/usr/bin/env python

from setuptools import setup

VERSION = '0.0.2'

setup(
    name='stakemachine',
    version=VERSION,
    description='Trading bot infrastructure for the DEX (BitShares)',
    long_description=open('README.md').read(),
    download_url='https://github.com/xeroc/stakemachine/tarball/' + VERSION,
    author='Fabian Schuh',
    author_email='Fabian@chainsquad.com',
    maintainer='Fabian Schuh',
    maintainer_email='Fabian@chainsquad.com',
    url='http://www.github.com/xeroc/stakemachine',
    keywords=['stake', 'bot', 'trading', 'api', 'blog', 'blockchain'],
    packages=[
        "stakemachine",
        "stakemachine.strategies",
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
            'stakemachine = stakemachine.cli:main',
        ],
    },
    install_requires=[
        "bitshares>=0.1.5",
        "prettytable",
        "click",
        "click-datetime",
        "colorama",
        "tqdm",
        "pyyaml",
        "sqlalchemy",
        "uptick",
    ],
    include_package_data=True,
)
