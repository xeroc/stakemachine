from __future__ import print_function
import sys
import shlex, shutil
import itertools
import click
from subprocess import Popen, PIPE
from collections import namedtuple


# whiptail.py - Use whiptail to display dialog boxes from shell scripts
# Copyright (C) 2013 Marwan Alsabbagh
# license: BSD, see LICENSE for more details.
# we have to bring this module in to fix up Python 3 problems

Response = namedtuple('Response', 'returncode value')


def flatten(data):
    return list(itertools.chain.from_iterable(data))

class Whiptail:

    def __init__(self, title='', backtitle='', height=20, width=60,
                 auto_exit=True):
        self.title = title
        self.backtitle = backtitle
        self.height = height
        self.width = width
        self.auto_exit = auto_exit
        
    def run(self, control, msg, extra=(), exit_on=(1, 255)):
        cmd = [
            'whiptail', '--title', self.title, '--backtitle', self.backtitle,
            '--' + control, msg, str(self.height), str(self.width)
        ]
        cmd += list(extra)
        p = Popen(cmd, stderr=PIPE)
        out, err = p.communicate()
        if self.auto_exit and p.returncode in exit_on:
            print('User cancelled operation.')
            sys.exit(p.returncode)
        return Response(p.returncode, str(err,'utf-8','ignore'))

    def prompt(self, msg, default='', password=False):
        control = 'passwordbox' if password else 'inputbox'
        return self.run(control, msg, [default]).value
    
    def confirm(self, msg, default='yes'):
        defaultno = '--defaultno' if default == 'no' else ''
        return self.run('yesno', msg, [defaultno], [255]).returncode == 0
    
    def alert(self, msg):
        self.run('msgbox', msg)
        
    def view_file(self, path):
        self.run('textbox', path, ['--scrolltext'])
        
    def calc_height(self, msg):
        height_offset = 8 if msg else 7
        return [str(self.height - height_offset)]
    
    def menu(self, msg='', items=(), prefix=' - '):
        if isinstance(items[0], string_types):
            items = [(i, '') for i in items]
        else:
            items = [(k, prefix + v) for k, v in items]
        extra = self.calc_height(msg) + flatten(items)
        return self.run('menu', msg, extra).value
    
    def showlist(self, control, msg, items, prefix):
        if isinstance(items[0], str):
            items = [(i, '', 'OFF') for i in items]
        else:
            items = [(k, prefix + v, s) for k, v, s in items]
        extra = self.calc_height(msg) + flatten(items)
        return shlex.split(self.run(control, msg, extra).value)
    
    def radiolist(self, msg='', items=(), prefix=' - '):
        return self.showlist('radiolist', msg, items, prefix)[0]
    
    def checklist(self, msg='', items=(), prefix=' - '):
        return self.showlist('checklist', msg, items, prefix)
    
    def view_text(self, text):
        """Whiptail wants a file but we want to provide a text string"""
        fd, nam = tempfile.mkstemp()
        f = os.fdopen(fd)
        f.write(text)
        f.close()
        self.view_file(nam)
        os.unlink(nam)


    def clear(self):
        # tidy up the screen
        click.clear()
        
class NoWhiptail:
    """
    Imitates the interface of whiptail but uses click only

    This is very basic CLI: real state-of-the-1970s stuff, 
    but it works *everywhere*
    """
    
    def prompt(self, msg, default='', password=False):
        return click.prompt(msg,default=default,hide_input=password)

    def confirm(self, msg, default='yes'):
        return click.confirm(msg,default=(default=='yes'))
    
    def alert(self, msg):
        click.echo(
            "[" +
            click.style("alert", fg="yellow") +
            "] " + msg
        )
        
    def view_text(self, text):
        click.echo_via_pager(text)
        
    def menu(self, msg='', items=(), prefix=' - ', default=0):
        click.echo(msg+'\n')
        if type(items) is dict: items = list(items.items())
        i = 1
        for k, v in items:
            click.echo("{:>2}) {}".format(i, v))
            i += 1
        click.echo("\n")
        ret = click.prompt("Your choice:",type=int,default=default+1)
        ret = items[ret-1]
        return ret[0]
        
    def radiolist(self, msg='', items=(), prefix=' - '):
        d = 0
        default = 0
        for k, v, s in items:
            if s == "ON":
                default = d
            d += 1
        return self.menu(msg,[(k,v) for k,v,s in items],default=default)


    def clear(self):
        pass # dont tidy the screen
    
def get_whiptail():
    if shutil.which("whyptail"):
        d = Whiptail()
    else:
        d = NoWhiptail() # use our own fake whiptail
    return d
