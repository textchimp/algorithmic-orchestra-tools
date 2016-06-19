#!/usr/bin/python

# Pipe OSC messages from TouchOSC mobile app to MIDI output and/or forward to Sonic Pi via OSC

# You will need to install the python-rtmidi and pyosc libraries; try one of these commands:
#
# $ pip install --pre python-rtmidi
# $ easy_install python-rtmidi

import socket, OSC, re, threading, math
import time, sys
from numpy import interp


import rtmidi
from rtmidi.midiutil import open_midiport
from rtmidi.midiconstants import *

SEND_SONIC = False  # set to true to send

# get machine's IP address, so we don't have to set it manually
import subprocess
ipaddr = subprocess.Popen(["ipconfig", "getifaddr", "en0"], stdout=subprocess.PIPE).communicate()[0].rstrip()
receive_address = ipaddr, 9000

# Sonic PI only accepts OSC connections from the same machine, i.e. localhost
send_address_pi = 'localhost',  4557


send_address_phone = '192.168.1.102', 9999   # your phone's IP address, for sending back current scale name, etc
phone = OSC.OSCClient()
try:
    phone.connect(send_address_phone)
except:
    print("phone: no connection")

def sendosc(client, path, args):
    msg = OSC.OSCMessage(path)
    msg.append(args)
    print msg
    client.send(msg)

mnote = 60
mchan = 0
chan_max = 6

last_note_time = 0
last_z_trig = 0
last_note = 0

last_z = 0
last_x = 0

z_reset = True
x_reset = True

hold_state = 0
mindex = 0

midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()
if available_ports:
    midiout.open_port(0)
else:
    midiout.open_virtual_port("My virtual output")



# START SCALE DEFINITIONS

current_scale = 0

MIDI_NOTE_MIN = 19
MIDI_NOTE_MAX = 109
MIDI_RANGE = MIDI_NOTE_MAX - MIDI_NOTE_MIN

MIN_VEL = 20
MAX_VEL = 80

instrument_names = ['Drums', 'Piano']

Test1 = [0, 2, 5, 6, 7]
Test2 = [0, 2, 4, 7, 8]
Test3 = [0, 3, 5, 8, 9]
Test4 = [0, 2, 6, 11]
Test5 = [0, 4, 7, 9]
Arabian = [0, 2, 4, 5, 6, 8, 10]
Balinese = [0, 1, 3, 7, 8]
Gypsy = [0, 1, 4, 5, 7, 8, 11]
MajorChord = [0, 4, 7]
MinorChord = [0, 3, 7]
Min7 = [0, 3, 7, 10]
Sus4 = [0, 5, 7]
Pelog = [0, 1, 3, 7, 10]
Major = [0, 2, 4, 5, 7, 9, 11]
Minor = [0, 2, 3, 5, 7, 8, 10]

scales = [Test1, Test2, Test3, Test4, Test5, Arabian, Balinese, Gypsy, MajorChord, MinorChord, Min7, Sus4, Pelog, Major, Minor]
scale_names =  ['Test1', 'Test2', 'Test3', 'Test4', 'Test5', 'Arabian', 'Balinese', 'Gypsy', 'MajorChord', 'MinorChord', 'Min7', 'Sus4', 'Pelog', 'Major', 'Minor']
#print(scales)
for s in range(0, len(scale_names)):
    print("[" + str(s) + "] " + scale_names[s])
print("\n------------- \n")
num_scales = len(scales)
sind = 0
scales_table = [[]] * num_scales
#print(scales_table[2])
#print(scales_table)
#print("len: " + str(num_scales))

key = 0
scale = 14

scale_group = [1,2,3,4,5]


# generate a true/false table of whether each note is 'on' in this position in scale
for sc in scales:
    #print("ind: " + str(sind))
    scales_table[sind] = [False]*12
    #print(scales_table[sind])
    for pos in sc:
        #print("pos: " + str(pos))
        scales_table[sind][pos] = True
    sind += 1
#print(scales_table)

# ugly ass 3D array init... so ugly and bad, but apparently necessary
scale_notes = [[]] * 12
for i in range(0, 12):
    scale_notes[i] = [[]] * num_scales
    for j in range(0, num_scales):
        scale_notes[i][j] = [[]] * 12


for key in range(0, 12):
    for s in range(0, num_scales):
        for k in range(0,12):
            relative_note = (key + k) % 12
            if scales_table[s][k] == True:
                scale_notes[key][s][relative_note] = True
            else:
                scale_notes[key][s][relative_note] = False

#print(scale_notes)

# ugly ass 3D array init
scale_midi_notes = [[]] * 12
#scale_midi_notecount = [[]] * 12
for i in range(0, 12):
    scale_midi_notes[i] = [[]] * num_scales
    #scale_midi_notecount[i] = [0] * num_scales
    for j in range(0, num_scales):
        scale_midi_notes[i][j] = [False] * MIDI_RANGE


# generate the list of valid midi notes for each scale in each key
for i in range(0, 12):
    for j in range(0, num_scales):
        note_count = 0
        for k in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX):
            if scale_notes[i][j][(k % 12)] == True:
                scale_midi_notes[i][j][note_count] = k
                note_count += 1
        scale_midi_notes[i][j] = scale_midi_notes[i][j][:note_count]   #truncate to only set values


# END SCALES

if len(sys.argv) > 2:
    current_scale = int(sys.argv[2])
    print "\n\nscale: " + scale_names[current_scale] + "\n\n"
else:
    current_scale = 6
    #balinese

if len(sys.argv) > 1:
    # minst = int(sys.argv[1])
    # # print minst
    SEND_SONIC = True


pi = OSC.OSCClient()
try:
    pi.connect(send_address_pi)
except:
    print("no connect")


# define a message-handler function for the server to call.
def test_handler(addr, tags, stuff, source):
    print("test_handler ---")
    print("received new osc msg from %s" % OSC.getUrlStr(source) )
    print("with addr : %s" % addr)
    print("typetags %s" % tags)
    print("data %s" % stuff)
    msg = OSC.OSCMessage()
    msg.setAddress(addr)
    msg.append(stuff)
    c.send(msg)
    print("return message %s" % msg)
    print("---")



def hold_handler(addr, tags, stuff, source):
    global hold_state
    if stuff[0] == 1.0:
        hold_state = 1
    else:
        hold_state = 0
    #mchan = int(stuff[0] * chan_max)
    #print mc

def chan_handler(addr, tags, stuff, source):
    global mchan
    #print addr, stuff
    mchan = int(stuff[0] * chan_max)
    print mchan

def scale_handler(addr, tags, stuff, source):
    global current_scale
    # set scale
    if stuff[0] < 1.0:
        # current_scale =  int ( interp(stuff[0], [0, 1], [0, len(scales) - 1 ]) )    #math.ceil( (len(scales) - 1 ) * stuff[0] )
        current_scale = int( (len(scales))  * stuff[0] )
        print len(scales), stuff[0], current_scale
        print "NEW scale: " + scale_names[current_scale] + " (" + str(current_scale) + ")"
        print

        sendosc(phone, "/1/labelscale", [ scale_names[current_scale] ])


def accxyz_handler(addr, tags, stuff, source):
    #print("typetags %s" % tags)
    #print("data %s \r" % stuff, end="")
    #print stuff[0]
    send_pi( stuff[0], stuff[1], stuff[2] )

def push_handler(addr, tags, stuff, source):
    if stuff[0] == 1.0:
        # send_osc( "play 90" )
        midiout.send_message([0x90 + mchan, 38, 100])

def pedal_handler(addr, tags, stuff, source):
    #if stuff[0] == 1.0:
    print("\npedal\n")
    midiout.send_message([0xb0 + mchan, 123, 0])


def send_osc(args):
    try:
        print args
        msg = OSC.OSCMessage("/run-code")
        #cmd = "play " + str(note) + ", attack: 0.001"
        msg.append([0, args])
        pi.send(msg)
        #pi.send( OSC.OSCMessage("/run", [22]) ) # why the fuck does this no longer work?
        # print "sent " + args
    except Exception as ex:
        print ex


def send_pi(accx, accy, accz):
    global last_note_time, last_note, last_z_trig, last_x, last_z, x_reset, z_reset, mnote, mindex

    fixedx = interp(accx,[-9.0, 9.0],[-0.5,0.5])
    note = int( 80 + (fixedx * 44) )

    vz = accz - last_z

    vx = accx - last_x
    #print "vz: " + str(vz) + " (z: " + str(accz) + ")"


    # print "z: " + str(accz)

    # Z-axis triggering using calculated Z-accel values...doesn't really work, or anyway not as well as just using the vz value
    # if 0 and vz < -20.0 and accz < -12.0:
    #     # silence
    #     print("\npedal\n")
    #     midiout.send_message([0xb0 + mchan, 123, 0])



    # yrot = interp(accy, [-9, 9], [0,1])
    # mnote = int( (yrot * 40) + 50 )


    try:
        sc = current_scale

        if hold_state:
            # hold current note ( but allow 1 note on either side of current note)
            span = 2
            xrot_hold = int(interp(accx, [-8, 8], [1, -1])) * span  # consider also [-3, 3] * 2 or  * 3 - more chord like?
            if mchan == 0:
                # drums, hold single note, i.e. drum
                mnote = mnote
            else:
                mind_hold = mindex + xrot_hold
                mnote = scale_midi_notes[key][current_scale][mind_hold]

        else:
            # calculate note based on x rotation, only if hold button not pressed

            xrot = interp(accx, [-10, 10], [1,0])
            #print xrot

            if mchan == 0:
                mnote = (xrot * 14) + 38
            else:
                mindex = int( (len(scale_midi_notes[key][current_scale])-1) *  xrot)  # yrot)
                mnote = scale_midi_notes[key][current_scale][mindex]
            #print "yrot mnote= " + str(mnote)

    except IndexError:
        print "nope: " + str(mindex) + ", max " + str(len(scale_midi_notes[key][sc]))

    # end calc


    # trigger on vz, ensure one direction only with accz positive check
    if vz > 4.0 and accz > 0 and z_reset :  #time.time() - last_z_trig > 0.01:

        z_reset = False
        zmag = interp(vz,[4.0, 30.0],[10, 110])
        print "TRIG vz: " + str(vz) + " (z: " + str(accz) + ") note: " + str(mnote) + " zvel: " + str(int(zmag)) + " (accy: " + str(accy) + ")"

        #print "play mnote= " + str( mnote )

        # fudge to ignore the regular triggering of the highest note from weird accel values
        if mnote != 108 :

            midiout.send_message([0x90 + mchan, mnote, int(zmag)]) #minst, int(zmag)])

            if SEND_SONIC: #and last_note != note and time.time() - last_note_time > 0.1:
                amp = interp(vz, [4.0, 45.0], [0.1, 1.2])
                ampstr = ", amp: " + str(amp)
                sus = interp(accy, [2, 9], [0, 0.5])
                sustainstr = ", attack: " + str(sus)
                send_osc( "set_sched_ahead_time! 0.01; use_synth :fm; play " + str(mnote) + ampstr + sustainstr )
                # last_note_time = time.time()

        last_z_trig = time.time()
        # print "z trig!"


    # trigger on x-axis shake too... doesn't work too well right now
    # if 0:
    #     if abs(vx) > 5.0 and x_reset :  #time.time() - last_z_trig > 0.01:
    #         x_reset = False
    #         # send_osc( "play 60" )
    #         xmag = interp(abs(vx),[5, 30],[30, 120])
    #         print "\nTRIG vx: " + str(vx) + " (z: " + str(accx) + ") xvel: " + str(int(xmag)) + " (accy: " + str(accy) + ") note " + str(mnote)
    #
    #         #print "play mnote= " + str( mnote )
    #         midiout.send_message([0x90 + mchan, mnote, int(xmag)]) #minst, int(zmag)])
    #
    #     if not x_reset and accx < 2.0 and accx > 0.0:
    #         x_reset = True
    #

    if not z_reset and accz <= 6.0:
        z_reset = True

    last_note = note
    last_z = accz
    last_y = accy

    # end send-pi function

s = OSC.OSCServer(receive_address)
s.addDefaultHandlers()
s.addMsgHandler("/accxyz", accxyz_handler)
s.addMsgHandler("/1/push7", push_handler)
s.addMsgHandler("/1/fader1", scale_handler)
s.addMsgHandler("/1/fader2", chan_handler)
s.addMsgHandler("/1/push1", pedal_handler) #top left
s.addMsgHandler("/1/push4", hold_handler) #top middle

for addr in s.getOSCAddressSpace():
    print( addr )

# Start OSCServer
print("\nStarting OSCServer. Use ctrl-C to quit.")
st = threading.Thread( target = s.serve_forever )
st.start()
# and that's it for the OSC

try :
    while 1 :
        time.sleep(1)

except KeyboardInterrupt :
    print ("\nClosing OSCServer.")
    s.close()
    print ("Waiting for Server-thread to finish")
    st.join() ##!!!
    print ("Done")
