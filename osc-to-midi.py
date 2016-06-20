#!/usr/bin/python
#
# Get OSC messages from Sonic Pi, and resend them as MIDI messages
#
# ZOMG!!! Suddenly all the riches of the Gigastudio sample world is available from Sonic Pi!

# NOTE: You will need the sonic-pi-init.rb in this folder - it will need to be saved as
#       ~/.sonic-pi/init.rb
#
# Then restart Sonic Pi, start this script, and you will be able to send MIDI notes
# by using the new functions 'posc' and 'pppt'
#
#

# You will need to install the rtmidi Python library, try one of these commands:
#
# $  pip install --pre python-rtmidi
#
# $ easy_install python-rtmidi
#
# ... and the same fom 'pyosc'
# ... and 'tkinter' (if you want to add trackpad control support to Sonic Pi)

# set this to true to send trackpad X Y values to Sonic Pi via OSC
SEND_MOUSE = True

import socket, OSC, re, threading, math, time, sys
import rtmidi
from rtmidi.midiutil import open_midiport
from rtmidi.midiconstants import *

from threading import Timer

from numpy import interp

import pdb

# this import seems to take a long time... why? how hard is mouse tracking?
if SEND_MOUSE:
    # import pymouse
    #import Tkinter as tk
    from Tkinter import *
    root = Tk()
    # Sonic PI only accepts OSC connections from the same machine, i.e. localhost
    send_address_pi = 'localhost',  4557
    pi = OSC.OSCClient()
    try:
        pi.connect(send_address_pi)
    except:
        print("ERROR: couldn't connect to sonic pi")



# import subprocess
# ipaddr = subprocess.Popen(["ipconfig", "getifaddr", "en0"], stdout=subprocess.PIPE).communicate()[0].rstrip()
receive_address = '127.0.0.1', 1122

midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()
midiout.open_virtual_port("Sonic Pi output")



if len(sys.argv) > 1:

    # test sending things when arg is set
    while True:
        print "play"
        midiout.send_message([ 0x90 + int(sys.argv[1]), 60, 80 ]) #minst, int(zmag)])
        time.sleep(2)

def send_osc(args):
    try:
        # print args
        msg = OSC.OSCMessage("/run-code")
        #cmd = "play " + str(note) + ", attack: 0.001"
        msg.append([0, args])
        pi.send(msg)
        #pi.send( OSC.OSCMessage("/run", [22]) ) # why the fuck does this no longer work?
        # print "sent " + args
    except Exception as ex:
        print ex

def noteoff(note, chan):
    midiout.send_message([ chan, note, 0])
    # print("note: " + str(note))


def note_handler(addr, tags, stuff, source):

    # [0, 1, 2, 3, *4] = note, vel, channel, pan, optional duration

    chan = stuff[2] - 1  #adjust channel to fit expected LinuxSampler setup
    note = stuff[0]

    if note == 0:
        print("pedal")
        midiout.send_message([0xb0 + chan, 123, 0])
        return

    if len(stuff) == 5:
        dur = stuff[4]
    else:
        dur = 1.0


    panmidi = int( interp(stuff[3], [-1, 1],[0, 127]) )
    velocity = int( interp(stuff[1], [0, 1],[0, 127]) )
    if velocity > 127:
        velocity = 127

    #print("pan: " + str(panmidi))

    # undocumented NRPN per-note panning for LinuxSampler:
    #1: CC 99, value 28
    #2: CC 98, note value 1-127
    #3: CC 06, pan value 1-127 (127 is full left?)
    midiout.send_message([ 176 + chan, 99, 28 ])
    midiout.send_message([ 176 + chan, 98, note ])
    midiout.send_message([ 176 + chan, 06, panmidi ])

    midiout.send_message([ 0x90 + chan, note, velocity ]) #minst, int(zmag)])
    if dur >= 0:
        Timer(dur, noteoff, [ note, 0x90 + chan] ).start()
        # offtimer[played_notes].start()

s = OSC.OSCServer(receive_address)
s.addDefaultHandlers()
s.addMsgHandler("/note", note_handler)

for addr in s.getOSCAddressSpace():
    print( addr )

# Start OSCServer
print("\nStarting OSCServer. Use ctrl-C to quit.")
st = threading.Thread( target = s.serve_forever )
st.start()
# and that's it for the OSC

def motion(event):
    x, y = event.x, event.y
    print('{}, {}'.format(x, y))

def dn(ev):
    print ev
#
if SEND_MOUSE:
    screen_width = float( root.winfo_screenwidth() )
    screen_height = float( root.winfo_screenheight() )
#     # mouse = pymouse.PyMouse()
#     root.bind('<Motion>', motion)
#     root.mainloop()
# else:

lastx = 0
lasty = 0

# root.bind('<Motion>', motion)
# root.bind('<Key>', dn)
# # pdb.set_trace()
# root.mainloop()


try :
    while True:
        if SEND_MOUSE:
            # print mouse.position()
            x = root.winfo_pointerx() / screen_width
            y = root.winfo_pointery() / screen_height
            if x > 0.999:
                x = 1.0
            if y > 0.999:
                y = 1.0
            #print x, y
            if x != lastx or y != lasty:
                # pdb.set_trace()
                send_osc("set_sched_ahead_time! 0.01; @mousex = %.4f ; @mousey = %.4f" % (x, y))
                lastx = x
                lasty = y
            time.sleep(0.001)
        else:
            time.sleep(1)

    #sys.stdin.readline()
except KeyboardInterrupt :
    print ("\nClosing OSCServer.")
    s.close()
    print ("Waiting for Server-thread to finish")
    st.join() ##!!!
    print ("Done")
