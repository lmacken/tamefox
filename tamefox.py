# tamefox.py - Put firefox to sleep when it does not have focus.
# Requirements: python-xlib python-psutil
# License: GPLv3+
# Author: Luke Macken <lmacken@redhat.com>
# Thanks to Jordan Sissel and Adam Jackson for their help

import os
import Xlib
import psutil

from signal import SIGSTOP, SIGCONT
from Xlib import X, display, Xatom

VERSION = '1.0'
TAME = ['Firefox', 'Chromium'] # Windows that we wish to tame

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


def wait_for_stop(process):
    while True:
        if process.status == psutil.STATUS_STOPPED:
            break


def send_signal(process, signal):
    process.send_signal(signal)
    for child in process.get_children():
        child.send_signal(signal)


def tamefox():
    """ Puts firefox to sleep when it loses focus """
    alive = True
    process = None
    try:
        for property, title, pid, event, parent in watch(['_NET_ACTIVE_WINDOW']):
            if parent in TAME:
                process = psutil.Process(pid)
                if not alive:
                    send_signal(process, SIGCONT)
                    alive = True
            elif process and alive:
                dpy.grab_server()
                dpy.sync()
                send_signal(process, SIGSTOP)
                wait_for_stop(process)
                dpy.ungrab_server()
                alive = False
    finally:
        if process and not alive:
            send_signal(process, SIGCONT)


if __name__ == '__main__':
    print "Tamefox v%s running..." % VERSION
    tamefox()
