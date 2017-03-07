#!/usr/bin/env python

from setuptools import setup

VERSION = '0.0.2'

setup(name='stakemachine',
      version=VERSION,
      description='Trading bot infrastructure for the DEX (BitShares)',
      long_description=open('README.md').read(),
      download_url='https://github.com/xeroc/stakemachine/tarball/' + VERSION,
      author='Fabian Schuh',
      author_email='<Fabian@BitShares.eu>',
      maintainer='Fabian Schuh',
      maintainer_email='<Fabian@BitShares.eu>',
      url='http://www.github.com/xeroc/stakemachine',
      keywords=['stake', 'bot', 'trading', 'api', 'blog', 'blockchain'],
      packages=["stakemachine",
                "stakemachine.strategies",
                ],
      classifiers=['License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python :: 3',
                   'Development Status :: 3 - Alpha',
                   'Intended Audience :: Developers',
                   ],
      entry_points={
          'console_scripts': [
              'stakemachine = stakemachine.__main__:main',
          ],
      },
      install_requires=["graphenelib==0.4.4",
                        "pyyaml",
                        "autobahn"
                        ],
      include_package_data=True,
      )
