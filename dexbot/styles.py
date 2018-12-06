""" This is helper file to print out strings in different colours
"""


def style(value, styling):
    return styling + value + '\033[0m'


def green(value):
    return style(value, '\033[92m')


def blue(value):
    return style(value, '\033[94m')


def yellow(value):
    return style(value, '\033[93m')


def red(value):
    return style(value, '\033[91m')


def pink(value):
    return style(value, '\033[95m')


def bold(value):
    return style(value, '\033[1m')


def underline(value):
    return style(value, '\033[4m')
