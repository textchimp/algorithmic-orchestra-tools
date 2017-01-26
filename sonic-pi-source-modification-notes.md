


The following changes need to be made to the Sonic Pi (version 2.11.1) code to allow SP to receive OSC messages from any machine on the network (required for receiving broadcasted sync messages):

/Applications/Sonic Pi.app/app/server/bin/sonic-pi-server.rb, approx line 70

Add `open: true` to the end of the line, i.e.:
```ruby
    osc_server = SonicPi::OSC::UDPServer.new(server_port, use_decoder_cache: true, open: true)
```

The following changes need to be made to add a default OSC message handler to Sonic Pi, so you can directly receive messages from TouchOSC (or anything else):

Same file as above,
/Applications/Sonic Pi.app/app/server/bin/sonic-pi-server.rb, approx line 350

```ruby
# set default handler method for any other OSC paths
osc_server.add_method("*") do |address, args|
  STDERR.puts "osc_default_handler(#{address.inspect}, #{args.inspect})"

  # nasty eval but the only way to access user-space methods?
  code = "osc_default_handler(#{address.inspect}, #{args.inspect}) if defined? osc_default_handler"

  sp.__spider_eval code, {external_source: 1}
end
```

/Applications/Sonic Pi.app/app/server/sonicpi/lib/sonicpi/osc/udp_server.rb, approx line 88:

```ruby
if @global_matcher
  @global_matcher.call(address, args)
else
  p = @matchers[address]
  if p
    p.call(args)
  elsif @matchers['*']
    @matchers['*'].call(address, args)  # default handler
```
