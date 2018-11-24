import os

"""
This is the unit test for print styles
"""

def style(s, style):
    return style + s + '\033[0m'


def green(s):
    return style(s, '\033[92m')


def blue(s):
    return style(s, '\033[94m')


def yellow(s):
    return style(s, '\033[93m')


def red(s):
    return style(s, '\033[91m')


def pink(s):
    return style(s, '\033[95m')


def bold(s):
    return style(s, '\033[1m')


def underline(s):
    return style(s, '\033[4m')


if __name__ == '__main__':
    # Unit test
    # Todo: Move tests to own files
    print(green("green style test"))
    print(blue("blue style test"))
    print(yellow("yellow style test"))
    print(red("red style test"))
    print(pink("pink style test"))
    print(bold("bold style test"))
    print(underline("underline test"))
