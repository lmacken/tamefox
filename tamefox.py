# tamefox.py -- Puts firefox to sleep when it does not have focus.
#
# License: GPLv2+
# Authors: Luke Macken <lewk@csh.rit.edu>
#          Jordal Sissel <jls@csh.rit.edu>

import os
import Xlib

from signal import SIGSTOP, SIGCONT
from Xlib import X, display, Xatom

def watch(properties):
    """ A generator that yields events for a list of X properties """
    dpy = display.Display()
    screens = dpy.screen_count()
    atoms = {}
    wm_pid = dpy.get_atom('_NET_WM_PID')

    for property in properties:
        atomid = dpy.get_atom(property, only_if_exists=True)
        if atomid != X.NONE:
            atoms[atomid] = property

    for num in range(screens):
        screen = dpy.screen(num)
        screen.root.change_attributes(event_mask=X.PropertyChangeMask)

    while True:
        ev = dpy.next_event()
        if ev.type == X.PropertyNotify:
            if ev.atom in atoms:
                data = ev.window.get_full_property(ev.atom, 0)
                id = int(data.value.tolist()[0])
                window = dpy.create_resource_object('window', id)
                if window.id == 0: continue
                pid = int(window.get_full_property(wm_pid, 0).value.tolist()[0])
                try:
                    title = window.get_full_property(Xatom.WM_NAME, 0).value
                except Xlib.error.BadWindow:
                    continue
                yield atoms[ev.atom], title, pid, data

def tamefox():
    """ Puts firefox to sleep when it loses focus """
    alive = True
    ff_pid = None
    for property, title, pid, event in watch(['_NET_ACTIVE_WINDOW']):
        if 'Mozilla Firefox' in title or title.endswith('Vimperator'):
            ff_pid = pid
            if not alive:
                print 'Waking up firefox'
                os.kill(ff_pid, SIGCONT)
                alive = True
        elif ff_pid and alive and not title.startswith('Opening') and \
                not title.startswith('PasswordMaker') and \
                title not in ('Authentication Required', 'Confirm', 'Alert',
                              'Downloads', 'Save As', 'Save a Bookmark',
                              'Add Security Exception', 'Print',
                              'File Upload', 'Clear Private Data',
                              'Delicious', 'Delicious account') \
                and not title.startswith('The page at') and \
                not title.startswith('Warning'):
            print 'Putting firefox to sleep'
            os.kill(ff_pid, SIGSTOP)
            alive = False

if __name__ == '__main__':
    tamefox()
