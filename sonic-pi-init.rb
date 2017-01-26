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
set_sched_ahead_time! 0.0001

require_relative '/Users/textchimp/oscencode.rb'

# acceptable synths (no noise or input)
@good_synths = synth_names - [:cnoise, :chipnoise, :bnoise, :gnoise, :mod_dsaw, :mod_pulse, :mod_saw, :noise, :pnoise, :sound_in, :sound_in_stereo]

# socket for sending OSC events to osc-to-midi.py server, to translate into MIDI note events
@oscmidi_socket = UDPSocket.new
@oscmidi_server, @oscmidi_port = '127.0.0.1', 1122


# socket for sending broacast cue triggers over the network
@osc_broadcast_socket = UDPSocket.new
# need to set this socket as having permission to send broadcast messages
@osc_broadcast_socket.setsockopt(Socket::SOL_SOCKET, Socket::SO_BROADCAST, true)



# IP address for broadcast will vary from network to network, but should be "inverse of netmask"
#
# @osc_broadcast_server = '192.168.1.255'
# @osc_broadcast_port = @oscmidi_port
#
# broadcast a cue over the network
# def netcue(*args)
#   @osc_broadcast_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/cue", args.map{|a| a.to_s }), 0, @osc_broadcast_server, @osc_broadcast_port)
#
# end

# Newer version, uses Sonic Pi OSC port 4557 directly (no intermediate Python server) but requires 'open: true' arg added to
# /Applications/Sonic Pi.app/app/server/bin/sonic-pi-server.rb (line 70):
# osc_server = SonicPi::OSC::UDPServer.new(server_port, use_decoder_cache: true, open: true)

@osc_broadcast_server = '169.254.255.255' # ad-hoc network
@osc_broadcast_port = 4557

def netcue(name, opts = {})
  time = opts[:time]   || 0
  count = opts[:count] || 0
  div = opts[:div]     || 0
  @osc_broadcast_socket.send(SonicPi::OSC::OscEncode.new.encode_single_message("/run-code",
    [0, "cue :#{name}, time: #{time.to_s}, count: #{count.to_s}, div: #{div.to_s}"]), 0, @osc_broadcast_server, @osc_broadcast_port)
end

# custom logging function
def cl(*str)
  File.open(Dir.home + '/.sonic-pi/log/lukeh.log', "a+") do |f|
    f.write str.to_s + "\n"
  end
end

# iterate over 2d array:
##| visiblematrix.each_with_index do |x, xi|
##|   x.each_with_index do |y, yi|
##|     puts "element [#{xi}, #{yi}] is #{y}"
##|   end
##| end

 ##| # use formatting function for val if defined (for returning strings from array indexes, etc
  ##| if formatter.is_a? Proc
  ##|   # use lambda formatting parameter
  ##|   val = formatter.call( val )
  ##| else
  ##|   if @touchosc_reply_format.key? path
  ##|     val = @touchosc_reply_format[path].call( val )
  ##|   end
  ##| end



def map_to_scale_note(s, min, max, n)

  norm = (min + n) / (max - min).to_f
  ind = (norm * (s.length-1)).to_i
  # puts min, max, n, "*******", norm, "[#{ind}]", s.length
  s[ind]
end


################ TouchOSC handling code

@touchosc_server, @touchosc_port = '192.168.1.107', 9999

@touchosc_update = {}

# we want each beat 1-16 to contain a column array of notes 1-8, which will be played simultaneously
@touchosc_notegrid = Array.new(16){ Array.new(8){0} }

# beats
@touchosc_beatgrid = Array.new(16){ Array.new(8){0} }


def touchosc_send(path, val)
  # puts "touchosc_send(): ", path, val
  # val must be an array
  begin
    @osc_broadcast_socket.send(
      SonicPi::OSC::OscEncode.new.encode_single_message(
    path, val), 0, @touchosc_server, @touchosc_port)
  rescue
    puts "(can't send)"
  end
end


def touchosc_reply(page, elem, id, label, val) #, formatter=nil)

  path = "/#{page}/#{elem}/#{id}"



  if elem == 'xy'
    # xy control
    ##| puts "REPLY: xy: ", page, elem, id, label, val
    path = "/#{page}/#{elem}/#{id}/label"
    touchosc_send(path, [label + ': ' + val.to_s])
    return
  elsif elem == 'toggle'
    path = "/#{page}/#{elem}/#{id}/label"
    touchosc_send(path, [label]) # + ': ' + val.to_s])
    return
  end

  puts "E", elem

  path = path +  "/val"
  touchosc_send(path, [val])

  path = "/#{page}/#{elem}/#{id}/name"
  touchosc_send(path, [label])

end



def touchosc_reset
  @touchosc_map.each do |key, val|
    if key.include? "/xy/"
      # this will run twice, unfortunately, once for the /x key and once for the /y
      key = key[0..-3] # strip end x/y
      val = [ @touchosc_map[key + '/y'], @touchosc_map[key + '/x'] ]
    else
      val = [val]
    end

    return if val.nil?
    puts "touchosc_reset():", key, val

    touchosc_send(key, val)
  end
end



def o(id, label, min_or_max=nil, max=nil) # , opts={})

  coord = ''

  # USE BLOCK INSTEAD?
  # keep this code as an example of how to add optional parameter arguments at end of function
  ##| # handle arg combinations
  ##| if opts.empty?
  ##|   if max.nil?
  ##|     puts "no opts 3rd, no max"
  ##|     min = 0
  ##|     max = min_or_max
  ##|     formatter = nil
  ##|   elsif max.is_a? Hash
  ##|     puts "no opts 3rd, max is hash"
  ##|     formatter = max[:f]
  ##|     min = 0
  ##|     max = min_or_max
  ##|   else
  ##|     puts "min, max set, no no hash"
  ##|     min = min_or_max
  ##|     formatter = nil
  ##|   end
  ##| else
  ##|   puts "min, max opts all set"
  ##|   min = min_or_max
  ##|   formatter = opts[:f]
  ##| end


  if id.is_a? Integer
    # default path is a page 1 fader, i.e. "/1/fader/4"

    page = '1'
    elem = 'fader'
    id = id.to_s

  else
    # treat as an OSC path, or shorthand

    parts = id.split('/')
    if parts.length == 4

      # full path, '/2/fader/3'
      _, page, elem, id = parts

    elsif parts.length == 2

      # shorthand, '2/3' style, page and id, assume fader: '/2/fader/3'
      page, id = parts
      elem = 'fader'

    elsif parts.length == 5

      # full path for xy control, with coord: '/2/xy/3/x'
      _, page, elem, id, coord = parts
      coord = '/' + coord

    elsif parts.length == 6
      #full path for multitoggle
      _, page, elem, id, y, x = parts
    else
      puts "NOT FOUND", id
      return 0
    end

  end   # id argument parsing

  path = '/' + page + '/' + elem + '/' + id + coord
  ##| puts "o() get path: " + path

  return 0 if not @touchosc_map.key? path

  # handle optional arguments
  if not min_or_max and not max

    # NO ARGS = treat as either button, or default range

    if elem == 'multitoggle'
      val = @touchosc_notegrid[y.to_i][x.to_i]
      return val
    elsif elem == 'toggle'
      # button type , true/false
      val = @touchosc_map[path].to_f > 0
      puts "TOGGLE", val
      return val
    else
      # treat as default range 0-1, i.e. do nothing with value provided by TouchOSC
      val = @touchosc_map[path].to_f
      puts "DEFAULT 0-1", val
    end

  else

    ##| use range to calculate value
    if max
      min = min_or_max.to_f
      max = max.to_f
    else
      min = 0
      max = min_or_max.to_f
    end
    val = @touchosc_map[path].to_f * (max - min).to_f + min

  end


  # use a hash to store values and only send update if value changed;
  # should save osc network traffic on updates which would otherwise
  # be sent on every sonic pi loop iteration
  if (not @touchosc_update.key? path) or val != @touchosc_update[path]

    puts "UPDATE send:", path, val, @touchosc_update
    @touchosc_update[path] = val

    val_reply = val   # use new var, in case original val is changed by block

    if block_given?

      val_reply = yield val

    elsif @touchosc_reply_format.key? path
      # use predefined format lambda from hash
      val_reply = @touchosc_reply_format[path].call( val )
    else
      val_reply = val_reply.round(3) if val_reply.is_a? Numeric
    end

    touchosc_reply(page, elem, id+coord, label, val_reply) #, formatter)

    ##| else
    ##|   puts "(no change in val)", path, val, @touchosc_update[path]
  end

  val  # actually return value for use in parameters
end


def notegrid_print
  @touchosc_notegrid.each_with_index do |x, xi|
    l = ''
    x.each_with_index do |y, yi|

      l += ((not y.nil? and y > 0.0) ? "x" : '.') #"[#{xi}, #{yi}] "
    end
    puts l
  end
end




def touchosc_recv(addr, val)

  val = val[0] if val.length == 1        # convert from array if necessary

  if addr.include? "/xy/"
    # special case for /1/xy/1/ controls, which we break into /x and /y keys
    @touchosc_map[ addr + '/x' ] = val[1]
    @touchosc_map[addr + '/y' ] = val[0]
    puts 'touchosc_recv() set xy = ', val
    return
  elsif addr.include? "/3/multitoggle/"  # TODO: make separate grids for each page/id multitoggle
    # multitoggle controls
    parts = addr.split('/')
    x = parts[5].to_i - 1
    y = parts[4].to_i - 1
    @touchosc_notegrid[x][y] = val
    return
  elsif addr.include? "/4/multitoggle/"
    # multitoggle controls
    parts = addr.split('/')
    x = parts[5].to_i - 1
    y = parts[4].to_i - 1
    @touchosc_beatgrid[x][y] = val
    return
  elsif addr.include? "/3/multifader/"
    # multitoggle controls
    parts = addr.split('/')
    n = parts[4].to_i - 1
    ##| y = parts[4].to_i - 1
    @touchosc_notefaders[n] = val
    return
  elsif addr.include? "/4/multifader/"
    # multitoggle controls
    parts = addr.split('/')
    n = parts[4].to_i - 1
    @touchosc_beatfaders[n] = val
    cl addr, val
    return
  elsif addr.include? "/push/"
    # run lambda function associated with this button
    cl "PUSH", addr, @touchosc_functions.key?(addr),  @touchosc_functions[addr]
    @touchosc_functions[addr].call if  @touchosc_functions.key? addr
    return
  end

  #default
  @touchosc_map[addr] = val
  puts "touchosc_recv() set: ", addr, @touchosc_map[addr]
end


#
#
# def touchosc_recv(addr, val)
#
#   val = val[0] if val.length == 1
#
#   if addr.include? "/xy/"
#     # special case for /1/xy/1/ controls, which we break into /x and /y keys
#     @touchosc_map[ addr + '/x' ] = val[1]
#     @touchosc_map[addr + '/y' ] = val[0]
#     puts 'touchosc_recv() set xy = ', val
#     return
#   elsif addr.include? "/3/multitoggle/"  # TODO: make separate grids for each page/id multitoggle
#     # multitoggle controls
#     parts = addr.split('/')
#     x = parts[5].to_i - 1
#     y = parts[4].to_i - 1
#     @touchosc_notegrid[x][y] = val
#     ##| puts "============ SET:", x, y, val
#
#     ##| notegrid_print
#     return
#   elsif addr.include? "/4/multitoggle/"  # TODO: make separate grids for each page/id multitoggle
#     # multitoggle controls
#     parts = addr.split('/')
#     x = parts[5].to_i - 1
#     y = parts[4].to_i - 1
#     @touchosc_beatgrid[x][y] = val
#     return
#   end
#
#   #default
#   @touchosc_map[addr] = val
#   puts "touchosc_recv() set: ", addr, val
# end


def touchosc_beatled(path, beat)
  touchosc_send(path + '/' + beat.to_s, [1.0])
  off = (beat - 1)
  ##| puts "=====", off
  off = 16 if off < 1
  touchosc_send(path + '/' + off.to_s, [0])
  # TODO: last LED in bar shown as white, to indicate beats/bar
end




# osc handler, avoid need for relay server
def osc_default_handler(address, args)
  # cl address, args
  touchosc_recv address, args
end

#################### end TouchOSC code

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

  # keyswitch = 0 if keyswitch.nil?
  keyswitch = -1 if keyswitch.nil?
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
@mousex_ctrl = 0
@mousey_ctrl = 0
@mousex_shift = 0
@mousey_shift = 0
@mousex_cmd = 0
@mousey_cmd = 0
@mousex_opt = 0
@mousey_opt = 0

@leap_x = 0
@leap_y = 0
@leap_z = 0
@leap_roll = 0
@leap_pinch = 0

def get_mousex(mod)
  case mod
  when :ctrl
    @mousex_ctrl
  when :shift
    @mousex_shift
  when :cmd
    @mousex_cmd
  when :opt
    @mousex_opt
  end
end

def get_mousey(mod)
  case mod
  when :ctrl
    @mousey_ctrl
  when :shift
    @mousey_shift
  when :cmd
    @mousey_cmd
  when :opt
    @mousey_opt
  end
end

# USAGE:
# mx(min, max, modifier)
# mx(min, max) [default modifier: SHIFT]
# mx(max, modifier)
# mx(max) [default modifier: SHIFT]
# mx(modifier)

def mx(*args)
  case args.length
  when 0
    @mousex_shift
  when 1
    if args[0].is_a? Numeric
      # range max, assume shift mod by default
      @mousex_shift * args[0]
    else
      # assume symbol, treat as key modifier
      get_mousex(args[0])
    end
  when 2
    if args[0].is_a? Numeric and args[1].is_a? Numeric
      # two numbers, treat as range
      @mousex_shift * (args[1] - args[0]) + args[0]
    elsif args[0].is_a? Numeric
      # first arg is number (max), second is symbol (key)
      get_mousex(args[1]) * args[0]
    end
  when 3
    # both min & max args, and also key mod
    get_mousex(args[2]) * (args[1] - args[0])  +  args[0]
    # @mousex_shift * (args[1] - args[0]) + args[0]
  end
end

def my(*args)
  case args.length
  when 0
    @mousey_shift
  when 1
    if args[0].is_a? Numeric
      # range max, assume shift mod by default
      @mousey_shift * args[0]
    else
      # assume symbol, treat as key modifier
      get_mousey(args[0])
    end
  when 2
    if args[0].is_a? Numeric and args[1].is_a? Numeric
      # two numbers, treat as range
      @mousey_shift * (args[1] - args[0]) + args[0]
    elsif args[0].is_a? Numeric
      # first arg is number (max), second is symbol (key mod)
      get_mousey(args[1]) * args[0]
    end
  when 3
    # both min & max args, and also key mod
    get_mousey(args[2]) * (args[1] - args[0])  +  args[0]
  end
end

# original version
#
# def my(*args)
#   case args.length
#   when 0
#     @mousey_shift
#   when 1
#     @mousey_shift * args[0]
#   when 2
#     @mousey_shift * (args[1] - args[0]) + args[0]
#   end
# end



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
