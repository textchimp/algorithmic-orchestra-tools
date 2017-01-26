# SEQUENCER
set_sched_ahead_time! 0.0001

##| @touchosc_notegrid = Array.new(16){Array.new(8){0}}
##| @touchosc_beatgrid = Array.new(16){Array.new(8){0}}

##| touchosc_reset

incoming_osc_debug_mode = true



@touchosc_notefaders = Array.new(16){ 1.0 }
@touchosc_beatfaders = Array.new(16){ 1.0 }

@touchosc_instmap = {
  3 => {
    name: 'piano',
    min: 21,
    max: 108
  },

}

@touchosc_drummap = {
  5 => :bd_klub,
  4 => :bd_klub,
  3 => :drum_snare_soft,
  2 => :bd_klub,
  1 => :drum_bass_hard
}
# ableton:

# ARDOUR / SOOPERLOOPER
# How to use Jackd for sonic pi (scsynth)

#hydro must open first, pi, then usb + jack

# start/stop pi buffer from touchosc?

# set up combined-virtual-device for builtin+usb so ardour can route to stereo(builtin)

# prevent sending weird keyswitches to sampler
# note  min

@hydrogen_from = 4
@hydrogen_channel = 16
@hydrogen_map = {
  4 => 36, # kick
  5 => 38, # floor tom
  6 => 39, # soft snare
  7 => 42, # hihat semi-open
  8 => 45 # stick
}

@touchosc_map = {
  '/1/fader/1' => 1.0,
  '/1/fader/2' => 1.0,
  '/1/fader/3' => 0.1,
  ##| '/1/fader/4' => 0.0,
  '/1/fader/5' => 1.0,
  '/1/fader/6' => 0.1,
  '/1/fader/7' => 0.4, # range: 1
  '/1/fader/8' => 0.0,
  '/1/xy/1/x'  => 0.1,
  '/1/xy/1/y'  => 0.1,
  '/1/xy/2/x'  => 0.6,
  '/1/xy/2/y'  => 0.1,
  '/1/xy/4/x'  => 0.5,

  '/1/xy/2/x' => 1.0,
  '/1/xy/2/y' => 1.0,
  '/1/xy/3/x' => 1.0,
  '/1/xy/3/y' => 1.0,


  '/2/toggle/1' => 1.0,


  '/3/fader/4'  => 0.6,  # octave
  '/3/fader/5'  => 0.6,  # bpm

  '/4/fader/6' => 1.0,  # beats per bar
  '/4/fader/4' => 0.5, # beat vel

  # just resets, not used to store incoming
  '/3/multifader/1/1' => 1.0,
  '/3/multifader/1/2' => 1.0,
  '/3/multifader/1/3' => 1.0,
  '/3/multifader/1/4' => 1.0,
  '/3/multifader/1/5' => 1.0,
  '/3/multifader/1/6' => 1.0,
  '/3/multifader/1/7' => 1.0,
  '/3/multifader/1/8' => 1.0,
  '/3/multifader/1/9' => 1.0,
  '/3/multifader/1/10' => 1.0,
  '/3/multifader/1/12' => 1.0,
  '/3/multifader/1/13' => 1.0,
  '/3/multifader/1/14' => 1.0,
  '/3/multifader/1/15' => 1.0,
  '/3/multifader/1/16' => 1.0,

  '/4/multifader/1/1' => 1.0,
  '/4/multifader/1/2' => 1.0,
  '/4/multifader/1/3' => 1.0,
  '/4/multifader/1/4' => 1.0,
  '/4/multifader/1/5' => 1.0,
  '/4/multifader/1/6' => 1.0,
  '/4/multifader/1/7' => 1.0,
  '/4/multifader/1/8' => 1.0,
  '/4/multifader/1/9' => 1.0,
  '/4/multifader/1/10' => 1.0,
  '/4/multifader/1/12' => 1.0,
  '/4/multifader/1/13' => 1.0,
  '/4/multifader/1/14' => 1.0,
  '/4/multifader/1/15' => 1.0,
  '/4/multifader/1/16' => 1.0,
}

@touchosc_functions = {
  # Clear note grid
  '/3/push/1' => lambda{
    cl 'CLEAR notes'
    @touchosc_notegrid.each_with_index do |x, xi|
      x.each_with_index do |y, yi|

        @touchosc_notegrid[xi][yi] = 0.0
        touchosc_send("/3/multitoggle/1/#{yi+1}/#{xi+1}", [0])

      end
    end
  },

  # Clear beat grid
  '/4/push/1' => lambda{
    @touchosc_beatgrid.each_with_index do |x, xi|
      x.each_with_index do |y, yi|

        @touchosc_beatgrid[xi][yi] = 0.0
        touchosc_send("/4/multitoggle/1/#{yi+1}/#{xi+1}", [0])

      end
    end
  }


}

@touchosc_reply_format = {
  '/1/fader/5' => lambda{ |val| @good_synths[val.to_i] }, #synth
  '/1/fader/7' => lambda{ |val| val.to_i } #bpm
}
##| with_fx :reverb do

def beatgrid_print
  @touchosc_beatgrid.each_with_index do |x, xi|
    l = ''
    x.each_with_index do |y, yi|

      l += ((not y.nil? and y > 0.0) ? "x" : '.') #"[#{xi}, #{yi}] "
    end
    puts l
  end
end


##| @touchosc_notegrid[0][2] = 0

##| @touchosc_notegrid[0][7] = 1
##| @touchosc_notegrid[8][3] = 1

@touchosc_beatgrid[6][6] = 1

##| sc = scale(:d2, :minor_pentatonic , num_octaves: 4)

beats = 16

with_fx :reverb do |rev|
  with_fx :distortion do |dist|
    with_fx :echo, slide: 0.2 do |ec|

      live_loop :bassz do |beat|

        # ABLETON LIVE
        ##| sync :live
        ##| beats.times do |beat|

        puts beat.to_i, "---------------------------------"
        touchosc_beatled('/3/led', beat)
        touchosc_beatled('/4/led', beat)

        if beat == 1
          ##| posc(notes[i], chan, vel: vel, pan: pan, dur: dur)

          posc(60, 1, vel: 1.0) #SOOPERLOOPER tap tempo

          notegrid_print

          ##| posc(2, 1, vel: 1.0) #MIDI start, triggger loops
        end

        control rev, mix: o(4, 'rev mix', 1)

        ##| control dist, mix: o(8, 'dist mix', 1)
        control dist, pre_mix: o(8, 'dist mix', 0.999)

        control ec,
          ##| slide: 2.0,
          ##| slide: 0.1,
          phase: o('/1/xy/4/x', 'e phase', 0.1, 2.0),
          mix:   o('/1/xy/4/y', 'e mix', 1.0)
        ##| decay: o(4, 'decay', 0.01, 1.0)

        sus = o(3, 'sus', 1)

        sc =  scale(
          :c4,
          scale_names[ o(1, 'scale', scale_names.length){|s| scale_names[s.to_i] }.to_i  ],
        num_octaves: o('1/7', 'range', 4).to_i)


        bd = sample_names :bd
        @touchosc_drummap[1] = bd[ o('/4/rotary/1', 'bass', bd.length){ |v| bd[v.to_i] }.to_i ]

        tabla = sample_names :tabla
        @touchosc_drummap[2] = tabla[ o('/4/rotary/2', 'tabla', tabla.length){ |v| tabla[v.to_i] }.to_i ]

        drum = sample_names :drum
        @touchosc_drummap[3] = drum[ o('/4/rotary/3', 'd1', drum.length){ |v| drum[v.to_i] }.to_i ]

        electro = sample_names :elec
        @touchosc_drummap[4] = electro[ o('/4/rotary/4', 'elec', electro.length){ |v| electro[v.to_i] }.to_i ]

        nrange =  o(6, 'offset', 12).to_i
        offset = rrand_i(-nrange, nrange)

        octave = o('/3/fader/4', 'oct', -4, 4){ |v| v.to_i }.to_i

        vel = o('/4/fader/4', 'vel', 1.0)

        amp = o(2, 'vol', 2)

        ##| n = sc[ o(1, 'root', sc.length).to_i + offset ]

        use_synth @good_synths[ o( 5, 'synth', @good_synths.length).to_i ]

        use_bpm o('/3/fader/5', 'bpm', 20, 300){ |v| v.to_i }.to_i

        att = o('/1/xy/1/x', 'atk', 0.0001, 0.8)
        rel = o('/1/xy/1/y', 'rel', 0.0001, 0.8)


        samlen = o('/1/xy/2/x', 's length', 0.0001, 1.0)
        samrate = o('/1/xy/2/y', 's rate', -2, 1)


        samstart = o('/1/xy/3/x', 's start', 1, 0)
        samlen = o('/1/xy/3/y', 's end')



        found = false

        note_col = @touchosc_notegrid[beat-1]
        ##| cl 'init', note_col, note_col.compact
        note_col = note_col.each_with_index.map do |val, n|
          if val > 0
            found = true
            map_to_scale_note(sc, 0,  7, n) + (octave * 12)
          else
            0  # might cause midi notes to stop?
          end
        end

        if false #found

          chan = 3
          if @touchosc_instmap.key? chan

            # remove notes out of range
            note_col.reject!{ |n| @touchosc_instmap[chan][:min] > n or n > @touchosc_instmap[chan][:max] }

            ##| posc(note_col.compact, 3, vel: vel) #if @touchosc_faders[beat-1] > rrand(0, 1)
            posc(note_col, 3, vel: 0.2)
          end

        else

          ##| cl 'col', note_col

          if found and @touchosc_notefaders[beat-1] > rrand(0, 1)

            play note_col,
              amp: amp, #vel
              ##| pan: pan,
              sustain: sus,
              attack: att, #o('/1/xy/1/x', 'atk', 0.0001, 0.8),
              release: rel
          end

        end

        # TODO: separate live_loop for separate fx
        beat_col = @touchosc_beatgrid[beat-1]
        beat_col.each_with_index.each do |val, n|
          if @touchosc_beatfaders[beat-1] > rrand(0, 1)
            if not val.nil? and val > 0
              ind = n+1
              if ind  >= @hydrogen_from
                posc(@hydrogen_map[ind], @hydrogen_channel, vel: vel )#0.8)
              else
                sam = @touchosc_drummap[ind]
                puts "______ sam", sam
                puts @touchosc_drummap, ind
                sample sam, finish: samlen, rate: samrate, start: samstart   if sam
              end
            end
          end
        end

        sleep 0.25 #o(2, 'sleep', 0.001,0.5)

        beats = o('/4/fader/6', 'num', 1, 16){ |v| v.to_i }.to_i

        beat %= beats
        beat += 1

        # end #ableton n.times

      end

    end #dist
  end #rev

end

##| end #rv
