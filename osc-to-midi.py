#!/usr/bin/python
#
# Get OSC messages from Sonic Pi, and resend them as MIDI messages
#
# This script also allows the current mouse position to be sent to Sonic Pi, to be used to control any numeric parameter.
#
# ZOMG!!! Suddenly all the riches of the Gigastudio sample world is available from Sonic Pi!

# NOTE: You will need the sonic-pi-init.rb in this folder - it will need to be saved as
#       ~/.sonic-pi/init.rb
#
# Then restart Sonic Pi, start this script, and you will be able to send MIDI notes
# by using the new functions 'posc' and 'pppt'
#
#

# If you want MIDI output support, you will need to install the rtmidi Python library.
#  Try one of these commands:
#
# $  pip install --pre python-rtmidi
#
# $ easy_install python-rtmidi
#
# ... and the same fom 'pyosc'
# ... and the same for 'tkinter' (if you want to add trackpad/mouse control support to Sonic Pi)



# set this to true to send trackpad X Y values to Sonic Pi via OSC (or command line option "mouse")
SEND_MOUSE = False

# set this to true to enable broadcasting of cue triggers over local network to anyone listening
SEND_CUE_BROADCAST = True

# MIDI off by default, enable on command line ("midi")
SEND_MIDI = False

import socket, OSC, re, threading, math, time, sys

from threading import Timer

from numpy import interp


# enable features from command line arguments: midi, mouse
if len(sys.argv) > 1:

    for arg in sys.argv[1:]:
        if arg.lower() == "midi":
            print "Using MIDI."
            SEND_MIDI = True
        elif arg.lower() == "mouse":
            print "Sending mouse position."
            SEND_MOUSE = True

    # # test sending things when arg is set
    # while True:
    #     print "play"
    #     midiout[1].send_message([ 0x90 + int(sys.argv[1]), 80, 80 ]) #minst, int(zmag)])
    #     time.sleep(2)



# this import seems to take a long time... why? how hard is mouse tracking?
if SEND_MOUSE:

    import Cocoa # for detecting modifier keys held down in OSX

    import Tkinter as tk
    # from Tkinter import *
    root = tk.Tk()
    # Sonic PI only accepts OSC connections from the same machine, i.e. localhost
    send_address_pi = 'localhost',  4557
    pi = OSC.OSCClient()
    try:
        pi.connect(send_address_pi)
    except:
        print("ERROR: couldn't connect to sonic pi")



receive_address = '', 1122  # don't care about destination address of incoming msg / use default address


# if SEND_CUE_BROADCAST:
#     send_address_pi = '192.168.1.255', receive_address[1]
#     # this will give a 'permission denied' error
#     # ...unless in OSC.py we can do something like "s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)"
#     osc_broadcast = OSC.OSCClient()
#     try:
#         osc_broadcast.connect(send_address_pi)
#     except:
#         print("ERROR: couldn't connect to cue broadcast address")
#


# MIDI port init

if SEND_MIDI:

    # only import if MIDI is enabled
    import rtmidi
    from rtmidi.midiutil import open_midiport
    from rtmidi.midiconstants import *

    USE_MULTIPLE_MIDI_PORTS = True

    if USE_MULTIPLE_MIDI_PORTS:
        midiout = []
        midiout.append( rtmidi.MidiOut() )
        # available_ports = midiout.get_ports()
        midiout[0].open_virtual_port("Sonic Pi output 0")
        midiout.append( rtmidi.MidiOut() )
        midiout[1].open_virtual_port("Sonic Pi output 1")
        #print(midiout)
    else:
        midiout = rtmidi.MidiOut()
        # available_ports = midiout.get_ports()
        midiout.open_virtual_port("Sonic Pi output")




def send_osc(args):
    try:
        #print args
        msg = OSC.OSCMessage("/run-code")
        msg.append([0, args]) # note undocumented first argument required by Sonic Pi
        pi.send(msg)
        #pi.send( OSC.OSCMessage("/run", [22]) ) # why the fuck does this no longer work?
        # print "sent " + args
    except Exception as ex:
        print ex


# for now we can do this from Sonic Pi, without getting the "permission denied" error
# def send_cue_broadcast(args):
#     try:
#         msg = OSC.OSCMessage("/cue")
#         msg.append([args])
#         osc_broadcast.send(msg)
#         print msg
#     except Exception as ex:
#         print ex
#

# thanks to: http://stackoverflow.com/questions/7514280/get-modifier-keys-which-have-been-pressed-while-starting-an-app-applescript
if SEND_MOUSE:
    def shift_held():
        # TODO: how to determine left or right key?
        return (Cocoa.NSEvent.modifierFlags() & Cocoa.NSShiftKeyMask) > 1

    def opt_held():
        return (Cocoa.NSEvent.modifierFlags() & Cocoa.NSAlternateKeyMask) > 1

    def cmd_held():
        return (Cocoa.NSEvent.modifierFlags() & Cocoa.NSCommandKeyMask) > 1

    def ctrl_held():
        return (Cocoa.NSEvent.modifierFlags() & Cocoa.NSControlKeyMask) > 1


def noteoff(note, port, chan):

    if USE_MULTIPLE_MIDI_PORTS:
        if port < len(midiout):
            midiport = midiout[port]
        else:
            midiport = midiout[0]
    else:
        midiport = midiout

    midiport.send_message([ chan, note, 0])
    # print("note: " + str(note))


def sendcue_handler(addr, tags, stuff, source):
    send_cue_broadcast(stuff[0])

def cue_handler(addr, tags, stuff, source):
    cue_name = stuff[0]
    count = stuff[1]
    time = stuff[2]
    div = stuff[3]
    send_osc("set_sched_ahead_time! 0.0001; cue :%s, count: %s, time: %s, div: %s;" % (cue_name, count, time, div))

def note_handler(addr, tags, stuff, source):

    #### [0, 1, 2, 3, *4] = note, vel, channel, pan, optional duration
    # [0, 1, 2, 3, 4, 5, 6] = note, vel, port, channel, pan, optional duration

    (note, vel, port, chan, pan, dur, keyswitch) = stuff

    print (note, vel, port, chan, pan, dur, keyswitch)

    chan -= 1  #adjust channel to fit expected LinuxSampler setup

    if USE_MULTIPLE_MIDI_PORTS:
        if port < len(midiout):
            midiport = midiout[port]
        else:
            midiport = midiout[0]
    else:
        midiport = midiout


    if note == 0:
        print("pedal")
        midiport.send_message([0xb0 + chan, 123, 0])  # CC 123 = silence
        return

    # if len(stuff) == 5:
    #     dur = stuff[4]
    # else:
    #     dur = 1.0

    panmidi = int( interp(pan, [-1, 1],[0, 127]) )
    velocity = int( interp(vel, [0, 1],[0, 127]) )
    if velocity > 127:
        velocity = 127

    #print("pan: " + str(panmidi)


    if keyswitch >= 0:
        print "keyswitch %d" % keyswitch, [0x90 + chan, keyswitch, 1]  # MUST BE 1!
        midiport.send_message( [0x90 + chan, keyswitch, 1])   # NoteOn for keyswitch (select instrument articulation)

    # undocumented NRPN per-note panning for LinuxSampler:
    #1: CC 99, value 28
    #2: CC 98, note value 1-127
    #3: CC 06, pan value 1-127 (127 is full left?)

    midiport.send_message([ 176 + chan, 99, 28 ])
    midiport.send_message([ 176 + chan, 98, note ])
    midiport.send_message([ 176 + chan, 06, panmidi ])

    # note
    midiport.send_message([ 0x90 + chan, note, velocity ]) #minst, int(zmag)])

    # set release
    if dur >= 0:
        Timer(dur, noteoff, [ note, port,  0x90 + chan] ).start()
        # offtimer[played_notes].start()

def default_handler(addr, tags, stuff, source):
    print "SERVER: No handler registered for ", addr
    return None

s = OSC.OSCServer(receive_address)
s.addDefaultHandlers()

if SEND_MIDI:
    s.addMsgHandler("/note", note_handler)

# s.addMsgHandler("/send_cue", sendcue_handler) # broadcast a cue from Sonic Pi on this machine

s.addMsgHandler("/cue", cue_handler) # deal with a cue received over the network

s.addMsgHandler("default", default_handler)

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
    if SEND_MOUSE:
        while True:
            # print mouse.position()
            x = root.winfo_pointerx() / screen_width
            y = root.winfo_pointery() / screen_height
            if x > 0.999:
                x = 1.0
            if y > 0.999:
                y = 1.0
            #print x, y
            if shift_held()  and (x != lastx or y != lasty):
                # # pdb.set_trace()
                send_osc("@mousex = %.4f ; @mousey = %.4f" % (x, y))
                lastx = x
                lasty = y
            time.sleep(0.001)
        # else:
        #     time.sleep(1)
    else:
        # wait for a ctrl-c
        while True:
            sys.stdin.readline()

except KeyboardInterrupt :
    print ("\nClosing OSCServer.")
    s.close()
    print ("Waiting for Server-thread to finish")
    st.join() ##!!!
    print ("Done")
