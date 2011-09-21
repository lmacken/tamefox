# tamefox.py - Put firefox to sleep when it does not have focus.
# License: GPLv2+
# Author: Luke Macken <lmacken@redhat.com>
# Thanks to Jordan Sissel and Adam Jackson for their help

import os
import Xlib

from signal import SIGSTOP, SIGCONT
from Xlib import X, display, Xatom

VERSION = '1.0'
TAME = ['Firefox'] # Windows that we wish to tame

dpy = display.Display()

def watch(properties):
    """ A generator that yields events for a list of X properties """
    screens = dpy.screen_count()
    atoms = {}
    wm_pid = dpy.get_atom('_NET_WM_PID')
    wm_client_leader = dpy.get_atom('WM_CLIENT_LEADER')

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
                parent = None
                try:
                    parent = window.get_full_property(wm_client_leader, 0).value.tolist()[0]
                    parent = dpy.create_resource_object('window', parent)
                    parent = parent.get_full_property(Xatom.WM_NAME, 0).value
                except Exception, e:
                    print str(e)
                try:
                    pid = int(window.get_full_property(wm_pid, 0).value.tolist()[0])
                    title = window.get_full_property(Xatom.WM_NAME, 0).value
                except (Xlib.error.BadWindow, Xlib.error.BadValue, AttributeError), e:
                    print str(e)
                    continue
                yield atoms[ev.atom], title, pid, data, parent

def wait_for_stop(pid):
    while True:
        statline = open("/proc/%d/stat" % pid)
        if statline.read().split()[2] == 'T':
            break
        statline.close()

def tamefox():
    """ Puts firefox to sleep when it loses focus """
    alive = True
    ff_pid = None
    pgid = None
    for property, title, pid, event, parent in watch(['_NET_ACTIVE_WINDOW']):
        if parent in TAME:
            ff_pid = pid
            pgid = os.getpgid(pid)
            if not alive:
                print 'Waking up firefox'
                os.killpg(pgid, SIGCONT)
                alive = True
        elif ff_pid and alive:
            print 'Putting firefox to sleep'
            dpy.grab_server()
            dpy.sync()
            os.killpg(pgid, SIGSTOP)
            wait_for_stop(ff_pid)
            dpy.ungrab_server()
            alive = False

if __name__ == '__main__':
    print "Tamefox v%s running..." % VERSION
    tamefox()
