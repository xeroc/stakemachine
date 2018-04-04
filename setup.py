#!/usr/bin/env python

from setuptools import setup
from setuptools.command.install import install
from distutils.util import convert_path

from pyqt_distutils.build_ui import build_ui

main_ns = {}
ver_path = convert_path('dexbot/__init__.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)
    VERSION = main_ns['__version__']


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
        "ruamel.yaml>=0.15.37"
    ],
    include_package_data=True,
)
