#!/usr/bin/env python

from setuptools import setup
from setuptools.command.install import install

from pyqt_distutils.build_ui import build_ui

VERSION = '0.1.2'


class InstallCommand(install):
    """Customized setuptools install command - converts .ui and .qrc files to .py files
    """
    def run(self):
        # Workaround for https://github.com/pypa/setuptools/issues/456
        self.do_egg_install()
        self.run_command('build_ui')


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
    cmdclass={
        'build_ui': build_ui,
        'install': InstallCommand,
    },
    entry_points={
        'console_scripts': [
            'dexbot = dexbot.cli:main',
        ],
    },
    install_requires=[
        "bitshares",
        "uptick>=0.1.4",
        "click",
        "sqlalchemy",
        "appdirs",
        "pyqt5",
        'pyqt-distutils',
        "ruamel.yaml",
        "sdnotify"
    ],
    include_package_data=True,
)
