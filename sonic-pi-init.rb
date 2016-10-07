# Sonic Pi init file
# Code in here will be evaluated on launch.
#
# NOTE: this file should be saved as ~/.sonic-pi/init.rb
#
# Any changes made here will require a restart of Sonic Pi to take effect.

# $LOAD_PATH << '~/.sonic-pi'

# osc send-to-midi!
#$LOAD_PATH << File.join(SonicPi::Util.root_path, "/app/server/sonicpi/lib/sonicpi/osc")
#require 'socket'

# need this for our run_code OSC calls to eval as realtime as possible
set_sched_ahead_time! 0.001

# socket for sending OSC events to osc-to-midi.py server, to translate into MIDI note events
@oscmidi_socket = UDPSocket.new
@oscmidi_server, @oscmidi_port = '127.0.0.1', 1122


# socket for sending broacast cue triggers over the network
@osc_broadcast_socket = UDPSocket.new

# IP address for broadcast will vary from network to network, but should be "inverse of netmask"
@osc_broadcast_server = '192.168.1.255'
@osc_broadcast_port = @oscmidi_port
# need to set this socket as having permission to send broadcast messages
@osc_broadcast_socket.setsockopt(Socket::SOL_SOCKET, Socket::SO_BROADCAST, true)

# broadcast a cue over the network
def netcue(*args)
  @osc_broadcast_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/cue", args.map{|a| a.to_s }), 0, @osc_broadcast_server, @osc_broadcast_port)

end

@last_channel = 0

def sendosc(note, vel, chan, pan, dur)
  note = *note  # wrap single value in array if necessary
  note.each do |n|
    @oscmidi_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/note", [n, vel, chan, pan, dur]), 0, @oscmidi_server, @oscmidi_port)
  end
  @last_channel = chan
end

#version of sendosc above but with optional keyword args
def posc(note, chan, opts = {})
  vel = opts[:vel].nil? ? 0.5 : opts[:vel]
  pan = opts[:pan] || 0
  int = opts[:int] || 0
  dur = opts[:dur] || -1
  speed = opts[:speed] ||= 1
  if chan.is_a? Array
    # calls to inst() return an array, otherwise we're getting the literal channel number
    port = chan[0]
    channel = chan[1]
    keyswitch = chan[2]
  else
    # pass it through if it's just a literal channel arg
    channel = chan
  end

  keyswitch = 0 if keyswitch.nil?
  port = 0 if port.nil?

  note = *note  # wrap single value in array if necessary
  note.each do |n|
    @oscmidi_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/note", [n, vel, port, channel, pan, dur, keyswitch]), 0, @oscmidi_server, @oscmidi_port)
    sleep int    if note.count > 1
    int *= speed if speed != 1
  end
  @last_channel = chan
end


# version of own ppt function but with optional keyword args
def pppt(notes, time, chan, opts = {})
  pan = opts[:pan] || 0
  dur = opts[:dur] || -1
  speed = opts[:speed] || 1
  vel = opts[:vel] || 0.5
  ppt(notes, time, speed, vel, chan, pan, dur)
end

def ppt(notes, time, speed, vel, chan, pan, dur)
  notes.length.times do |i|
    #sendosc(notes[i], vel, chan, pan, dur)
    posc(notes[i], chan, vel: vel, pan: pan, dur: dur)
    sleep time
    if speed != nil
      time *= speed
    end
  end
  @last_channel = chan
end


def silence(*args)
  if args.length == 0
    chan = @last_channel
  else
    chan = args[0]
  end
  #sendosc(0, 0, chan, 0, 0)
  posc(0, chan, vel: 0)
end

# inst - get MIDI port/channel/keyswitch values for inst/artic symbol names
# args: [0] inst name symbol [1](optional) artic symbol
# ret:  array [port, chan, keyswitch] (keyswitch will be nil if no such artic)
#
# NOTE: relies on @instruments instance variable to be correctly defined
#
def inst(*args)
  name = args[0]
  if @instruments.key?(name)
    chan = @instruments[name][:channel]
    port = @instruments[name][:port]
  end
  if args.length == 2 and @instruments[name].key?(:articulations)
    artic_keyswitch = @instruments[name][:articulations][ args[1] ]
  end
  [port, chan, artic_keyswitch]
end



# mouse/trackpad control code!
# needs osc-to-midi.py script to be running to receive values over OSC
#
# usage:
#
# mx()       : return a float between 0 and 1 representing the position of the
#              mouse/trackpad pointer on the screen (0 = full left, 1 = full right)
#
# mx(n)      : return a float between 0 and n based on the pointer position
#
# mx(n1, n2) : return a float between n1 and n2 proportional to the pointer position
#
# same for my()  (0 = top of screen, 1 = bottom)

@mousex = 0
@mousey = 0

@leap_x = 0
@leap_y = 0
@leap_z = 0
@leap_roll = 0
@leap_pinch = 0

def mx(*args)
  case args.length
  when 0
    @mousex
  when 1
    @mousex * args[0]
  when 2
    @mousex * (args[1] - args[0]) + args[0]
  end
end

def my(*args)
  case args.length
  when 0
    @mousey
  when 1
    @mousey * args[0]
  when 2
    @mousey * (args[1] - args[0]) + args[0]
  end
end



# misc utility fns

def vr(*arr)
  # return a ring of values (for amplitude) based on dividing array values by 10
  # i.e. vr( 1,2,3 )     =>    (ring 0.1, 0.2, 0.3)
  arr.map{ |a| a / 10.0 }.ring
end

def volring(arr, p, f)
  arr.map{ |a|
    if a
      f
    else
      p
    end
  }.ring
end


# # LinuxSampler MIDI instrument mappings
# <articulation name="Pluck" keyswitch="91"/>
# <articulation name="Quick scratchy" keyswitch="90"/>
# <articulation name="Cresc/Dim 9s" keyswitch="89"/>
# <articulation name="5s bow, hard attack" keyswitch="88"/>
# <articulation name="16s bow, hard attack" keyswitch="87"/>
# <articulation name="1s bow" keyswitch="86"/>
# <articulation name="0.5s bow" keyswitch="85"/>
# <articulation name="0.3s bow" keyswitch="84"/>

# TREM SUS? SUS? need more clarity

string_articulations = {
  piz: 91,
  stac: 90,
  bow03: 84,
  bow05: 85,
  bow1: 86,
  bow5: 88,
  bow: 87,
  credim: 89
}
cello_articulations = {
  stac: 24,   # "C0"
  bow03: 25,
  bow05: 26,
  sus: 27,
  sfz: 28,
  credim: 29,
  trem: 30,
  piz: 31
}

@instruments = {
  piano: {
    port: 0,
    channel: 3,
    note_min: 20,
    note_max: 40,
  },
  guitar: {
    port: 0,
    channel: 12,
    articulations: string_articulations
  },
  bass: {
    port: 0,
    channel: 6,
    articulations: string_articulations
  },
  cello: {
    port: 0,
    channel: 2,
    articulations: cello_articulations
  },
  viola: {
    port: 0,
    channel: 5,
    articulations: cello_articulations
  }
}
