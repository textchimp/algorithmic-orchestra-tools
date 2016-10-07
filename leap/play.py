#!/usr/bin/python
#
# Leap Motion "Invisible Piano" v0.1b
# By Luke Hammer 2016 for the Algorithmic Orchestra
#
# Packages required:
#
# Leap Motion SDK v2.3.1 (?)
# - Note that this script expects to find 'Leap.py', 'LeapPython.so' and 'libLeap.dylib' in the same folder
#   (These files are provided by the SDK in the lib/ folder)
#
# - rtmidi (`pip install --pre python-rtmidi` or `easy_install python-rtmidi`)
# - pyosc  (`pip install --pre pyosc` or `easy_install pyosc`)
# - readchar (`pip install --pre readchar` or `easy_install readchar`)
# - numpy  (`pip install --pre numpy` or `easy_install numpy`)
#
#
# This script will let you communicate with Sonic Pi via OSC pretty easily,
# but if you want the full orchestra sample experience, you will need the following:
#
#  - LinuxSampler plus Fantasia frontend: http://www.linuxsampler.org/downloads.html
#  - Awesome piano sample library: http://download.linuxsampler.org/instruments/pianos/maestro_concert_grand_v2.rar (~1GB uncompressed)
#  - Possibly a program like Midi Patchbay (on OSX) to connect the MIDI output port from
#    this script to LinuxSampler: http://notahat.com/midi_patchbay/
#
# TODO:
#  - consider using an 'adaptive plane' such as the vertical 'touch emulation' supported by the SDK,
#    so the Y play threshold is not absolute, but moves relative to the hand - could be easier for people to learn to play
#
#  - LOOPS: left thumb pinch starts loop, any note starts and stops are recorded to loop until fingers are unpinched, which
#           sets loop length and starts playback of loop (i.e. multiple non-synced loops playing at once?)

import os, sys, inspect, thread, time
src_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
arch_dir = '../lib/x64' if sys.maxsize > 2**32 else '../lib/x86'
sys.path.insert(0, os.path.abspath(os.path.join(src_dir, arch_dir)))
import Leap
from Leap import CircleGesture, KeyTapGesture, ScreenTapGesture, SwipeGesture, Bone

from threading import Timer
import threading
import Queue

import socket, OSC

import math

import readchar

import rtmidi
from rtmidi.midiutil import open_midiport
from rtmidi.midiconstants import *

from numpy import interp


ALLFINGER_MODE = 0
ONEFINGER_MODE = 1
play_mode = ALLFINGER_MODE #ONEFINGER_MODE

# import pygame
# pygame.init()
# pygame.display.set_mode()

# Sonic PI only accepts OSC connections from the same machine, i.e. localhost
send_address_pi = 'localhost',  4557
USE_OSC = False

if USE_OSC:
    # temporary assumption that we only want to send one finger's data to Sonic Pi
    play_mode = ONEFINGER_MODE


send_address_browser = 'localhost',  57121
BROWSER_OSC = False #True

if BROWSER_OSC:
    # temporary assumption that we only want to send one finger's data to Sonic Pi
    play_mode = ONEFINGER_MODE

#
# if len(sys.argv) > 1:
#     # minst = int(sys.argv[1])
#     # # print minst
#     SEND_SONIC = True


# default MIDI channel, i.e. instrument
# you will need to change this depending on your sampler setup
# (you might also need to subtract 1 from the channel number
#  your sampler reports when setting this var; don't ask me why)
channel = 2

current_scale = 0
current_key = 0

# we do specific note calculation for drum sequencer:
# this assumes Hydrogen as our drum machine, but which channel depends on your setup
DRUM_CHANNEL = 0

DEBUG = 0
if DEBUG:
    import pdb


FINGER_VELOCITY_Y = -600
FINGER_VELOCITY_RANGE = [600, 1000]

PLANEY = 200.0                  # Note trigger Y plane height
PLANEY_SILENCE = PLANEY + 80.0  # Y height which hand must cross in upward motion, to trigger silence
VELY_SILENCE = 600.0            # Y minimum velocity hand must be travelling at to trigger silence

SILENCE_MIN_INTERVAL = 0.5      # Minimum time between triggering silence, in seconds

last_silence_time = 0

VELOCITY_RANGE =  [20, 90]   #[20, 110]      # output MIDI velocity range

DRUM_RANGE = [ 36, 50 ]

# indexes into hand arrays
LEFT = 1
RIGHT = 0

hands_crossed_plane = [ [False] * 5, [False] * 5 ]  # track if fingers cross the Y plane for playing
                                                    # [0][4] is right hand, pinky finger

hands_last_note = [ [0] * 5, [0] * 5 ]              # track last note played by each finger, for 'hold' effect

hands_note_ypos = [ [0] * 5, [0] * 5 ]              # y pos at last note play (to check if re-crossed)
hands_note_time = [ [0] * 5, [0] * 5 ]              # time last note played for each finger

hands_finger_bend = [ [0] * 5, [0] * 5 ]            # amount of bend for each finger

last_note =  {} #{'note': 0, 'x': 0, 'y': 0, 'z':0, 'finger': 0}

swipe_rec = []

loops = []
loop_counter = 0
current_rec_loop = []

REC_OFF = 0
REC_ON = 1
REC_UPDATE = 2
REC_STOP = 3

rec_state = REC_OFF

record_queue = Queue.Queue()

# setup MIDI
midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()
midiout.open_virtual_port("Leap Motion output")

MIDI_NOTE_MIN = 19
MIDI_NOTE_MAX = 109
MIDI_RANGE = MIDI_NOTE_MAX - MIDI_NOTE_MIN

panmidi = 64

if USE_OSC:
    pi = OSC.OSCClient()
    try:
        pi.connect(send_address_pi)
    except:
        print("ERROR: no connection to Sonic Pi OSC server")
        USE_OSC = False


if BROWSER_OSC:
    browser = OSC.OSCClient()
    try:
        browser.connect(send_address_browser)
    except:
        print("ERROR: no connection to browser/websockets server")
        BROWSER_OSC = False

# Scale definitions

Arabian = [0, 2, 4, 5, 6, 8, 10]
Balinese = [0, 1, 3, 7, 8]
Gypsy = [0, 1, 4, 5, 7, 8, 11]
MajorChord = [0, 4, 7]
MinorChord = [0, 3, 7]
Min7 = [0, 3, 7, 10]
Sus4 = [0, 5, 7]
Maj7 = [0, 4, 7, 11]
Shiva = [2, 4, 9, 11]
Oriental = [0, 1, 4, 5, 6, 9, 10]
Pelog = [0, 1, 3, 7, 10]
Major = [0, 2, 4, 5, 7, 9, 11]
Minor = [0, 2, 3, 5, 7, 8, 10]

# A full list of scales
# Major=[0, 2, 4, 5, 7, 9, 11]
# Minor=[0, 2, 3, 5, 7, 8, 10]
# MajorChord=[0, 4, 7]
# MinorChord=[0, 3, 7]
# Min7=[0, 3, 7, 10]
# Sus4=[0, 5, 7]
# WholeTone=[0, 2, 4, 6, 8, 10]
# Blues=[0, 2, 3, 5, 6, 7, 9, 10,11]
MajorPentatonic=[0, 2, 4, 5, 7]
# NeapolitanMinor=[0, 1, 3, 5, 7, 8, 11]
# NeapolitanMajor=[0, 1, 3, 5, 7, 9, 11]
# Oriental=[0, 1, 4, 5, 6, 9, 10]
# DoubleHarmonic=[0, 1, 4, 5, 7, 8, 11]
# Enigmatic=[0, 1, 4, 6, 8, 10, 11]
# Hirajoshi=[0, 2, 3, 7, 8]
# HungarianMinor=[0, 2, 3, 6, 7, 8, 11]
# HungarianMajor=[0, 3, 4, 6, 7, 9, 10]
# Kumoi=[0, 1, 5, 7, 8]
# Iwato=[0, 1, 5, 6, 10]
# Hindu=[0, 2, 4, 5, 7, 8, 10]
# Spanish8Tone=[0, 1, 3, 4, 5, 6, 8, 10]
# Pelog=[0, 1, 3, 7, 10]
# HungarianGypsy=[0, 2, 3, 6, 7, 8, 10]
# MajorPhrygian=[0, 1, 4, 5, 7, 8, 10]
# MajorLocrian=[0, 2, 4, 5, 6, 8, 10]
# LydianMinor=[0, 2, 4, 6, 7, 8, 10]
# Overtone=[0, 2, 4, 6, 7, 9, 10]
# LeadingWholeTone=[0, 2, 4, 6, 8, 10, 11]
# Arabian=[0, 2, 4, 5, 6, 8, 10]
# Balinese=[0, 1, 3, 7, 8]
# Gypsy=[0, 1, 4, 5, 7, 8, 11]
# Mohammedan=[0, 2, 3, 5, 7, 8, 11]
# Javanese=[0, 1, 3, 5, 7, 9, 10]
# Persian=[0, 1, 4, 5, 6, 8, 11]
# Algerian=[0, 2, 3, 6, 7, 8, 11]


# set which scales are available to the app
# the scale currently in use is mapped to the Z-axis for now

scales = [Balinese, Minor, Maj7, MajorPentatonic]
scale_names =  ['Balinese',  'Minor', 'Maj7', 'MajorPentatonic']
# scales = [Test1, Test2, Test3, Test4, Test5, Arabian, Balinese, Gypsy, MajorChord, MinorChord, Min7, Sus4, Pelog, Major, Minor]
# scale_names =  ['Test1', 'Test2', 'Test3', 'Test4', 'Test5', 'Arabian', 'Balinese', 'Gypsy', 'MajorChord', 'MinorChord', 'Min7', 'Sus4', 'Pelog', 'Major', 'Minor']



# Best to ignore the following messy scale table init code
#################################################################################
for s in range(0, len(scale_names)):
    print("[" + str(s) + "] " + scale_names[s])
print("\n------------- \n")
num_scales = len(scales)
sind = 0
scales_table = [[]] * num_scales

# generate a true/false table of whether each note is 'on' in this position in scale
for sc in scales:
    #print("ind: " + str(sind))
    scales_table[sind] = [False]*12
    #print(scales_table[sind])
    for pos in sc:
        #print("pos: " + str(pos))
        scales_table[sind][pos] = True
    sind += 1

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

############################################# END scale init horror



# Leap Motion listener

class SampleListener(Leap.Listener):

    finger_names = ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']
    bone_names = ['Metacarpal', 'Proximal', 'Intermediate', 'Distal']
    state_names = ['STATE_INVALID', 'STATE_START', 'STATE_UPDATE', 'STATE_END']


    def on_connect(self, controller):
        print "Connected"

        # keep processing when app not focused
        controller.set_policy(Leap.Controller.POLICY_BACKGROUND_FRAMES)

        # Enable gestures - lots to play with here
        #
        # controller.enable_gesture(Leap.Gesture.TYPE_CIRCLE);
        # controller.enable_gesture(Leap.Gesture.TYPE_SCREEN_TAP);


        # controller.enable_gesture(Leap.Gesture.TYPE_SWIPE);
        # controller.enable_gesture(Leap.Gesture.TYPE_KEY_TAP);

        controller.config.set("Gesture.Swipe.MinLength", 100.0) #100
        controller.config.set("Gesture.Swipe.MinVelocity", 750) #750
        controller.config.save()

    def on_frame(self, controller):

        global last_silence_time, note, swipe_rec, panmidi, last_note, rec_state

        frame = controller.frame()

        # use frontmost finger to set current scale from Z axis
        scale_change = 1
        front = frame.pointables.frontmost
        if front.is_valid:
            scale_change = int( interp(front.tip_position.z, [-160, 200], [ len(scales)-1, 0 ]) )

        tracked_fingers = []
        if play_mode == ONEFINGER_MODE:
            tracked_fingers.append( frame.pointables.frontmost )
        elif play_mode == ALLFINGER_MODE:
            tracked_fingers = frame.pointables

        for pointable in tracked_fingers:
        #for pointable in frame.pointables:

            # example attributes for pointable[0]:
            # 'frame', 'hand', 'id', 'invalid', 'is_extended', 'is_finger', 'is_tool', 'is_valid', 'length', 'stabilized_tip_position',
            #'this', 'time_visible', 'tip_position', 'tip_velocity', 'touch_distance', 'touch_zone', 'width'
            #
            # po[0].hand.is_left
            #
            # "A Hand.confidence rating indicates how well the observed data fits the internal model."

            if not pointable.is_valid:
                continue

            if pointable.hand.is_left:
                handid = LEFT
            else:
                handid = RIGHT

            # the pointable id is new each time the hand is lost and refound,
            # but it always ends in a 0 to 4, to indicate thumb to little finger
            fingerid = pointable.id % 10

            fingervel = pointable.tip_velocity
            fingerpos = pointable.tip_position

            # pinch is a float from 0 to 1 for how close the thumb tip is to touching the next finger tip
            # - using this for note 'hold'
            pinch = pointable.hand.pinch_strength

            if handid == LEFT:
                if pinch > 0.9:
                    rec_state = REC_ON
                else:
                    rec_state = REC_OFF


            if USE_OSC:
                # print "y: %.2f\r\n" % (interp(fingerpos.z, [-200, 200], [1, 0]))
                # TODO: some time-based throttling here
                send_sonicpi_code( "@leap_x = %.4f; @leap_y = %.4f;  @leap_z = %.4f; @leap_pinch = %.4f" %
                (interp(fingerpos.x, [-250, 250], [0, 1]),
                interp(fingerpos.y, [20, 700], [0, 1]),    # all these xyz ranges arrived at by observation/trial&error
                interp(fingerpos.z, [-200, 200], [1, 0]),
                pinch))
                # could use [200, -350] for Z... but range gets lower as hand gets closer to sensor

            if BROWSER_OSC:
                # print "y: %.2f\r\n" % (interp(fingerpos.z, [-200, 200], [1, 0]))
                # TODO: some time-based throttling here
                # send_sonicpi_code( "@leap_x = %.4f; @leap_y = %.4f;  @leap_z = %.4f; @leap_pinch = %.4f" %
                send_browser_osc([
                 interp(fingerpos.x, [-100, 100], [0, 1]),
                 interp(fingerpos.y, [20, 400], [0, 1]),
                 interp(fingerpos.z, [-200, 200], [1, 0]), pinch
                ])

            # grab is a float from 0 to 1 for how much the whole hand is closed into a fist
            # - using this to play notes of shorter duration
            grab = pointable.hand.grab_strength



            # hands_finger_bend[handid][fingerid] = finger_bend( Leap.Finger(pointable) )

            # if True: #fingerid == 1:
            #     sys.stdout.write("\r%.2f    %.2f    %.2f    %.2f   %.2f "
            #     % (hands_finger_bend[handid][0], hands_finger_bend[handid][1], hands_finger_bend[handid][2], hands_finger_bend[handid][3], hands_finger_bend[handid][4]))
            #     #sys.stdout.write("\rPLAY [%d][%d] %.2f (%d : v=%d) Z = %.2f sc: %s ; p = %.2f, g = %.2f touch = %.2f"
            #     #% (handid, fingerid, fingervel.y, note, vel, fingerpos.z, scale_names[scale_change], pinch, grab, pointable.touch_distance  ))
            #     sys.stdout.flush()

            # PLAY NOTE ON 'PLANEY' THRESHOLD CROSS
            # but only if the finger was previously above the threshold
            # (is the y velocity test necessary??)


            # new play of finger when y velocity > a value
            # threshold defined by y pos at time of velocity trigger, no notes until recrossed or time limit

            if hands_crossed_plane[handid][fingerid] == True and fingerpos.y > hands_note_ypos[handid][fingerid]:

                # print "\r\nRESET %.1f" % fingerpos.y
                hands_crossed_plane[handid][fingerid] = False

            if True:

                # velocity-based play! easier! no absolute Y plane to pass! Y-plane is per-finger per per-note

                if fingervel.y < FINGER_VELOCITY_Y and time.time() - last_silence_time > 0.2 and (
                hands_crossed_plane[handid][fingerid] == False or time.time() - hands_note_time[handid][fingerid] > 0.2 ):

                    # print "play!"
                    hands_note_time[handid][fingerid] = time.time()

                    vel = int( interp(abs(fingervel.y), FINGER_VELOCITY_RANGE, VELOCITY_RANGE) )

                    if pinch > 0.8:
                        note = hands_last_note[handid][fingerid]
                        print "\r\nPINCH"
                    else:
                        maxind = len(scale_midi_notes[current_key][scale_change ]) - 1
                        noteindex = int( interp(fingerpos.x, [-250, 250], [0, maxind]) )
                        note = scale_midi_notes[key][scale_change][noteindex]

                    hands_crossed_plane[handid][fingerid] = True
                    hands_note_ypos[handid][fingerid] = fingerpos.y;
                    hands_last_note[handid][fingerid] = note  # keep track of last note played, for hold effect


                    # undocumented NRPN per-note panning for LinuxSampler:
                    #1: CC 99, value 28
                    #2: CC 98, note value 1-127
                    #3: CC 06, pan value 1-127 (127 is full left?)
                    midiout.send_message([ 176 + channel, 99, 28 ])
                    midiout.send_message([ 176 + channel, 98, note ])
                    midiout.send_message([ 176 + channel, 06, panmidi ])
                    # print "pan: %d" % panmidi

                    if DEBUG:
                        sys.stdout.write("\rPLAY [%d][%d] %.2f (%d : v=%d) Z = %.2f sc: %s ; p = %.2f, g = %.2f touch = %.2f"
                        % (handid, fingerid, fingervel.y, note, vel, fingerpos.z, scale_names[scale_change], pinch, grab, pointable.touch_distance  ))
                        sys.stdout.flush()

                    # this works but doesn't give a smooth slide between notes TODO: check docs
                    if channel == 14 and note != last_note['note']:
                        #hands_last_note[handid][fingerid]
                        print "(sil)"
                        # midiout.send_message([0x80 + channel, note, 0]) #noteoff to create continuous movement
                        noteoff(last_note['note'], 0x90 + channel)

                    midiout.send_message([ 0x90 + channel, note, vel ])

                    if grab > 0.5:
                        dur = (1 - grab) * 2
                        Timer(dur, noteoff, [ note, 0x90 + channel] ).start()
                    else:
                        dur = 0

                    last_note = {'note': note, 'channel': channel, 'vel': vel, 'dur': dur, 'pan': panmidi, 'x': fingerpos.x, 'y': fingerpos.y, 'z':fingerpos.z, 'finger': pointable}

                    # commented for DEMO
                    # if rec_state == REC_ON:
                    #     print "\r\nPUT\r\n", last_note
                    #     record_queue.put(last_note, False)


            elif hands_crossed_plane[handid][fingerid] == False and fingerpos.y <= PLANEY: # and fingervel.y < 0.0:

                # get note velocity (volume) from finger Y-axis velocity at moment it crosses threshold
                vel = int( interp(abs(fingervel.y), [50, 2000], VELOCITY_RANGE) )

                # if thumb and forefinger are pinched, use 'hold' mode, i.e. keep playing same notes for each finger
                if pinch > 0.8:
                    note = hands_last_note[handid][fingerid]
                else:

                    if channel == DRUM_CHANNEL:
                        # use a special range of notes (approx 36-50) for the drum sampler channel (i.e. Hydrogen drum machine)
                         note = int( interp(fingerpos.x, [-250, 250], DRUM_RANGE) )
                    else:
                        # calculate note from X-axis position, left is lower, right is higher, like a real piano
                        # i.e. our X-axis position is mapped to an index into all the notes in the current scale's array
                        maxind = len(scale_midi_notes[current_key][scale_change]) - 1
                        noteindex = int( interp(fingerpos.x, [-250, 250], [0, maxind]) )
                        try:
                            # getting some IndexError exceptions here when changing between scales (Z-axis movement)
                            # TODO: better array bounds checking
                            # if noteindex >= 0 and noteindex < len(scale_midi_notes[key][scale_change]):
                                # if scale_change >= 0 and scale_change < len(scales):
                            note = scale_midi_notes[key][scale_change][noteindex]
                        except IndexError:
                            pass

                    hands_last_note[handid][fingerid] = note  # keep track of last note played, for hold effect


                if DEBUG:
                    sys.stdout.write("\rPLAY [%d][%d] %.2f (%d : v=%d) Z = %.2f sc: %s ; p = %.2f, g = %.2f touch = %.2f"
                    % (handid, fingerid, fingervel.y, note, vel, fingerpos.z, scale_names[scale_change], pinch, grab, pointable.touch_distance  ))
                    sys.stdout.flush()


                hands_crossed_plane[handid][fingerid] = True

                midiout.send_message([ 0x90 + channel, note, vel ])

                if USE_OSC:
                    # here's a simple example of sending some code to sonic pi
                    # note that this only plays a single note
                    # TODO: to modify parameters of a running synth, you'd probably have to do
                    # something clever with function definitions or global variables
                    # TODO: think of all the parameters you could control with hand XYZ values, rotation values, gesture values

                    amp = interp(abs(fingervel.y), [50, 2000], [0.1, 1.2])
                    sustain = 1.0 - grab  # use degree of fistiness

                    if DEBUG:
                        # this will overwrite the MIDI output debug line above
                        sys.stdout.write("\rset_sched_ahead_time! 0.01; use_synth :fm; play %d, amp: %.4f, sustain: %.4f                     "
                        % (note, amp, sustain))
                        sys.stdout.flush()

                    send_sonicpi_code( "set_sched_ahead_time! 0.01 ; use_synth :beep ; play %d, amp: %.4f, sustain: %.5f" % (note, amp, sustain))



                # use hand 'grab' state to set note length:
                # - fully closed fist = very short notes
                # - more open fist = longer notes
                # - fully open hand = no note end
                if grab > 0.5:
                    dur = (1 - grab) * 2
                    Timer(dur, noteoff, [ note, 0x90 + channel] ).start()


            # reset 'thresold plane crossed' flag
            elif hands_crossed_plane[handid][fingerid] == True and fingerpos.y > (PLANEY):

                # print "PLANE RESET [%d][%d] %.2f" % (handid, fingerid, fingerpos.y)
                hands_crossed_plane[handid][fingerid] = False




        # Get hands - currently just used for 'silence' gesture,
        # i.e. the gesture depends on whole palm movement, not any one finger
        for hand in frame.hands:

            palm_position = hand.palm_position
            palm_velocity = hand.palm_velocity
            palm_normal = hand.palm_normal

            roll = 180.0 * palm_normal.roll / math.pi
            panmidi = interp(roll, [-90, 90], [1, 127])

            if USE_OSC:
                send_sonicpi_code( "@leap_roll = %.4f;" % ( interp(roll, [-90, 90], [1, 0]) ) )


            # sys.stdout.write("\rnorm: %.2f" % (interp(roll, [-90, 90], [-1.0, 1.0])))
            # sys.stdout.flush()

            # silence gesture
            if palm_velocity.y > VELY_SILENCE and palm_position.y > last_note['y']: #PLANEY_SILENCE:
                if time.time() - last_silence_time > SILENCE_MIN_INTERVAL:
                    print "SILENCE"
                    #print last_note
                    silence(channel)
                    last_silence_time =  time.time()

            # examples of hand values, not used (from SDK Sample.py)
            # if False:
            #     handType = "Left hand" if hand.is_left else "Right hand"
            #
            #     print "  %s, id %d, position: %s" % (
            #         handType, hand.id, hand.palm_position)
            #
            #     # Get the hand's normal vector and direction
            #     normal = hand.palm_normal
            #     direction = hand.direction
            #
            #     # Calculate the hand's pitch, roll, and yaw angles
            #     print "  pitch: %f degrees, roll: %f degrees, yaw: %f degrees" % (
            #         direction.pitch * Leap.RAD_TO_DEG,
            #         normal.roll * Leap.RAD_TO_DEG,
            #         direction.yaw * Leap.RAD_TO_DEG)
            #
            #     # Get arm bone
            #     arm = hand.arm
            #     print "  Arm direction: %s, wrist position: %s, elbow position: %s" % (
            #         arm.direction,
            #         arm.wrist_position,
            #         arm.elbow_position)
            #
            #     # Get fingers
            #     for finger in hand.fingers:
            #
            #         print "    %s finger, id: %d, length: %fmm, width: %fmm" % (
            #             self.finger_names[finger.type],
            #             finger.id,
            #             finger.length,
            #             finger.width)
            #
            #         # Get bones
            #         for b in range(0, 4):
            #             bone = finger.bone(b)
            #             print "      Bone: %s, start: %s, end: %s, direction: %s" % (
            #                 self.bone_names[bone.type],
            #                 bone.prev_joint,
            #                 bone.next_joint,
            #                 bone.direction)
            #

        # Get gestures - not using these yet (from SDK Sample.py)
        # if True:
        #     for gesture in frame.gestures():
        #
        #         #if self.state_names[gesture.state] == 'STATE_END':
        #
        #         if gesture.type == Leap.Gesture.TYPE_CIRCLE:
        #             circle = CircleGesture(gesture)
        #
        #             # Determine clock direction using the angle between the pointable and the circle normal
        #             if circle.pointable.direction.angle_to(circle.normal) <= Leap.PI/2:
        #                 clockwiseness = "clockwise"
        #             else:
        #                 clockwiseness = "counterclockwise"
        #
        #             # Calculate the angle swept since the last frame
        #             swept_angle = 0
        #             if circle.state != Leap.Gesture.STATE_START:
        #                 previous_update = CircleGesture(controller.frame(1).gesture(circle.id))
        #                 swept_angle =  (circle.progress - previous_update.progress) * 2 * Leap.PI
        #
        #             print "  Circle id: %d, %s, progress: %f, radius: %f, angle: %f degrees, %s" % (
        #                     gesture.id, self.state_names[gesture.state],
        #                     circle.progress, circle.radius, swept_angle * Leap.RAD_TO_DEG, clockwiseness)
        #
        #         if gesture.type == Leap.Gesture.TYPE_SWIPE:
        #             swipe = SwipeGesture(gesture)
        #             #only track the swipe of 1 finger, not all
        #             if swipe.pointable == frame.pointables.frontmost:
        #                 if gesture.state == Leap.Gesture.STATE_START: #self.state_names[gesture.state] == 'STATE_START':
        #                     pass#print "\nSTART"
        #
        #                     #swipe_rec = []
        #                 elif gesture.state == Leap.Gesture.STATE_UPDATE: #self.state_names[gesture.state] == 'STATE_UPDATE':
        #                     #print "\nUPDATE"
        #                     swipe_rec.append( swipe.direction )
        #                 elif gesture.state == Leap.Gesture.STATE_STOP: #self.state_names[gesture.state] == 'STATE_END':
        #
        #                     # work out type of gesture based on average xy movement
        #                     ax = ay = az = 0
        #                     i = 0
        #                     for vec in swipe_rec:
        #                         #print vec
        #                         ax += vec.x
        #                         ay += vec.y
        #                         az += vec.z
        #                         i += 1
        #                     if i > 0:
        #                         ax /= i
        #                         ay /= i
        #                         az /= i
        #
        #                     if abs(ax) > abs(ay): #abs(ay) < 0.5 and abs(ax) > 0.5:
        #
        #                         print "  Swipe id: %d, state: %s, position: %s, direction: %s, speed: %f (pointable: %s)" % (
        #                                 gesture.id, self.state_names[gesture.state],
        #                                 swipe.position, swipe.direction, swipe.speed, swipe.pointable)
        #                         if swipe.direction.x > 0:
        #                             print "\nRIGHT SWIPE"
        #                         else:
        #                             print "\nLEFT SWIPE"
        #
        #
        #                         print "\n\nx: %.2f, y: %.2f, z: %.2f\n\n" % (ax, ay, az)
        #                         swipe_rec = []
        #
        #                     else:
        #                         pass #print "ax: %.2f, ay: %.2f" % (ax, ay)
        #
        #
        #                 elif gesture.state == Leap.Gesture.STATE_INVALID:
        #                     print "\nINVALID\n"
        #                 else:
        #                     print "unknown: %s" % self.state_names[gesture.state]
        #
        #         if gesture.type == Leap.Gesture.TYPE_KEY_TAP:
        #             if gesture.state == Leap.Gesture.STATE_STOP:
        #                 keytap = KeyTapGesture(gesture)
        #                 # if  keytap.pointable == frame.pointables.frontmost:
        #                 print "  Key Tap id: %d, %s, position: %s, direction: %s" % (
        #                         gesture.id, self.state_names[gesture.state],
        #                         keytap.position, keytap.direction )
        #                 print keytap.pointable
        #
        #         if gesture.type == Leap.Gesture.TYPE_SCREEN_TAP:
        #             screentap = ScreenTapGesture(gesture)
        #             print "  Screen Tap id: %d, %s, position: %s, direction: %s" % (
        #                     gesture.id, self.state_names[gesture.state],
        #                     screentap.position, screentap.direction )


    def state_string(self, state):
        if state == Leap.Gesture.STATE_START:
            return "STATE_START"

        if state == Leap.Gesture.STATE_UPDATE:
            return "STATE_UPDATE"

        if state == Leap.Gesture.STATE_STOP:
            return "STATE_STOP"

        if state == Leap.Gesture.STATE_INVALID:
            return "STATE_INVALID"


# calculate degree of bend of finger using dot product of two bones
# returns: float indicating 'bentness' of finger: 1.0 is straight, 0.0 is fully curled
# ( https://community.leapmotion.com/t/measure-the-bending-finger-in-leap-motion-c/1036/8 )
def finger_bend( finger ):
    proximal = finger.bone(Bone.TYPE_PROXIMAL)
    distal = finger.bone(Bone.TYPE_DISTAL)
    dot = proximal.direction.dot(distal.direction)
    return 1.0 - (1.0 + dot) / 2.0;

# change MIDI channel, i.e. instrument
def setchan(ch, label):
    global channel
    silence(channel)
    channel = ch
    print ""
    print "New instrument: %s" % label

# silence a specific note
def noteoff(note, chan):
    midiout.send_message([ chan, note, 0])
    # print("note: " + str(note))

# silence all playing notes
def silence(chan):
    midiout.send_message([0xb0 + chan, 123, 0])


def send_browser_osc(args):
    try:
        msg = OSC.OSCMessage("/hand")
        msg.append([args])
        browser.send(msg)
        # pi.send( OSC.OSCMessage("/run-code", [22]) ) # why the fuck does this no longer work?
        # print "sent " + args
    except Exception as ex:
        print ex



# send code string to sonic pi
def send_sonicpi_code(args):
    try:
        msg = OSC.OSCMessage("/run-code")
        msg.append([0, args])
        pi.send(msg)
        # pi.send( OSC.OSCMessage("/run-code", [22]) ) # why the fuck does this no longer work?
        # print "sent " + args
    except Exception as ex:
        print ex


def setmode(mode):
    global play_mode
    play_mode = mode
    print "\r\nMODE = %d" % mode


def looper(rec_queue, controller):
    global hands_last_note, loop_counter
    rec_last = REC_OFF
    tick = 0
    TICK_LENGTH = 0.1 # 100ms
    print "looper() start"

    while True:

        # print rec_state

        if rec_state == REC_ON and rec_state != rec_last:
            # just started recording
            # print "\r\nREC start"
            rec_last = rec_state
            current_rec_loop = []
        elif  rec_state == REC_OFF and rec_state != rec_last:
            # just stopped recording
            # print "\r\nREC stop"

            loops.append(current_rec_loop)

            rec_last = rec_state


        # print "looper()"

        #
        # sys.stdout.write("\rrec: %d    last %d" % (rec_state, rec_last))   #("\rPLAY [%d][%d] %.2f (%d : v=%d) Z = %.2f sc: %s ; p = %.2f, g = %.2f touch = %.2f"
        # # % (handid, fingerid, fingervel.y, note, vel, fingerpos.z, scale_names[scale_change], pinch, grab, pointable.touch_distance  ))
        # sys.stdout.flush()
        try:
            note = rec_queue.get(False)

            current_rec_loop.append(note)
            print "\r\nev", ev

        except Queue.Empty:
           ev = None

        time.sleep(0.01)


        # while interval < TICK_LENGTH:
        #     time.sleep(0.01)

        # or

        # if(time_since_last_tick >= TICK_LENGTH):
        #     tick += 1


def main():

    # set up controller and listener
    listener = SampleListener()
    controller = Leap.Controller()

    # Have the sample listener receive events from the controller
    controller.add_listener(listener)

    # basically need a thread to do looping here only because of the blocking keyboard input in main()
    t = threading.Thread(target=looper, args=(record_queue, controller) )#, args = (q,u))
    t.daemon = True
    t.start()

    # Keep this process running until Enter or space or ctrl+c is pressed
    print "Press Enter or Ctrl+C to quit."
    print "Press 1 to 0 to change instruments..."
    # try:
    while True:
        # print "l"
        # for event in pygame.event.get():
        #     if event.type == pygame.QUIT:
        #         pygame.quit(); #sys.exit() if sys is imported
        #     if event.type == pygame.KEYDOWN:
        #         if event.key == pygame.K_0:
        #             print("Hey, you pressed the key, '0'!")

        print ""
        char = readchar.readkey()
        if char == '\r' or char == ' ' or char == '\x03':
            controller.remove_listener(listener)
            sys.exit(0)

        # the following channel-to-instrument mappings are for my LinuxSampler setup;
        # yours will probably be different (remember you may need to subtract 1 from the channel shown in Linuxsampler)
        elif char == '1':
            setchan(2, "Piano")
        elif char == '2':
            setchan(3, "Harp")
        elif char == '3':
            setchan(6, "Violin (fast)")
        elif char == '4':
            setchan(5, "Cello (plucked)")
        elif char == '5':
            setchan(14, "Clarinet Ensemble (sustained)")
        elif char == '6':
            setchan(8, "Acoustic Guitar")
        elif char == '7':
            setchan(4, "Strings (sustained)")
        elif char == '8':
            setchan(15, "Double Bass piz.")
        elif char == '9':
            setchan(1, "Viola sus.")
        elif char == '0':
            setchan(0, "Drums")

        elif char == 'm':

            setmode(not play_mode)

if __name__ == "__main__":
    main()
