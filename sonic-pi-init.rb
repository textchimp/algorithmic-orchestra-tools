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



def sendosc(note, vel, chan, pan, dur)
  note = *note  # wrap single value in array if necessary
  note.each do |n|
    @oscmidi_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/note", [n, vel, chan, pan, dur]), 0, @oscmidi_server, @oscmidi_port)
  end
end

#version of sendosc above but with optional keyword args
def posc(note, chan, opts = {})
  vel = opts[:vel].nil? ? 0.5 : opts[:vel]
  pan = opts[:pan] || 0
  int = opts[:int] || 0
  dur = opts[:dur] || -1
  speed = opts[:speed] ||= 1
  note = *note  # wrap single value in array if necessary
  note.each do |n|
    @oscmidi_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/note", [n, vel, chan, pan, dur]), 0, @oscmidi_server, @oscmidi_port)
    sleep int    if note.count > 1
    int *= speed if speed != 1
    #puts [n, vel, chan, pan, dur]
  end
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
    sendosc(notes[i], vel, chan, pan, dur)
    sleep time
    if speed != nil
      time *= speed
    end
  end
end

def silence(chan)
  sendosc(0, 0, chan, 0, 0)
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
