# tamefox.py - Puts firefox & chromium to sleep when they do not have focus.
#
# Requirements: python-xlib python-psutil
#
# Author: Luke Macken <lmacken@redhat.com>
# Thanks to Jordan Sissel and Adam Jackson for their help
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2008-2013  Luke Macken <lmacken@redhat.com>

import time
import psutil
import psutil.error

from signal import SIGSTOP, SIGCONT
from Xlib import X, display, Xatom

VERSION = '1.4'
TAME = ['Firefox', 'Chromium', 'Google Chrome']  # Windows that we wish to tame

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
                if window.id == 0:
                    continue
                parent = None
                try:
                    parent = window.get_full_property(wm_client_leader, 0)
                    parent = parent.value.tolist()[0]
                    parent = dpy.create_resource_object('window', parent)
                    parent = parent.get_full_property(Xatom.WM_NAME, 0).value
                except Exception, e:
                    print(str(e))
                try:
                    pid = window.get_full_property(wm_pid, 0)
                    pid = int(pid.value.tolist()[0])
                    title = window.get_full_property(Xatom.WM_NAME, 0).value
                except Exception, e:
                    print(str(e))
                    continue
                yield atoms[ev.atom], title, pid, data, parent


def wait_for_stop(process):
    while True:
        if process.status == psutil.STATUS_STOPPED:
            break


def send_signal(process, signal):
    action = signal is SIGSTOP and 'Stopping' or 'Continuing'
    print('%s %s' % (action, process.name))
    process.send_signal(signal)
    for child in process.get_children():
        print('%s %s' % (action, child.name))
        child.send_signal(signal)


def tame():
    processes = {}
    awake = []

    def stop(process):
        time.sleep(1.0)  # Let wm animations finish
        dpy.grab_server()
        dpy.sync()
        try:
            send_signal(process, SIGSTOP)
            wait_for_stop(process)
            awake.remove(process.pid)
        except psutil.error.NoSuchProcess:
            awake.remove(process.pid)
            del(processes[process.pid])
        finally:
            dpy.ungrab_server()

    def cont(process):
        pid = process.pid
        if pid in awake:
            return
        try:
            send_signal(process, SIGCONT)
            if pid not in awake:
                awake.append(pid)
        except psutil.error.NoSuchProcess:
            del(processes[pid])
            if pid in awake:
                awake.remove(pid)

    try:
        for prop, title, pid, event, parent in watch(['_NET_ACTIVE_WINDOW']):
            try:
                proc = psutil.Process(pid)
            except psutil.error.NoSuchProcess:
                continue
            if parent in TAME and pid not in processes:
                processes[pid] = proc
                awake.append(pid)
            if pid in processes:
                for process in processes.values():
                    cont(process)
                for other in [p for p in awake if p != pid]:
                    stop(processes[other])
            elif proc.ppid in processes:
                if proc.ppid not in awake:
                    cont(proc.parent)
            else:
                for running in [p for p in awake]:
                    stop(processes[running])
    finally:
        for process in processes.values():
            try:
                if process.status == psutil.STATUS_STOPPED:
                    cont(process)
            except psutil.error.NoSuchProcess:
                pass


if __name__ == '__main__':
    print("Tamefox v%s running..." % VERSION)
    try:
        tame()
    except KeyboardInterrupt:
        pass
