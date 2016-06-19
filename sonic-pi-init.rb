# Sonic Pi init file
# Code in here will be evaluated on launch.

# $LOAD_PATH << '~/.sonic-pi'

# osc send-to-midi!
#$LOAD_PATH << File.join(SonicPi::Util.root_path, "/app/server/sonicpi/lib/sonicpi/osc")
#require 'socket'

@oscmidi_socket = UDPSocket.new
@oscmidi_server, @oscmidi_port = '127.0.0.1', 1122

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
