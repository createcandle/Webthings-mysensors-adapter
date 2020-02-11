# MySensors-adapter

This is an adapter for the Mozilla WebThings Gateway that allows it to connect to MySensors devices.

MySensors is an Arduino framework that makes it easy to create your own smart devices, such as sensors for your smart home. They are generaly connected wirelessly, and can form a mesh network together, allowing the network to reach further.
https://www.mysensors.org

This adapter connects your MySensors network to the Mozilla WebThings Gateway, which is an open source smart home controller built by the Mozilla Foundation. You might know them from the Firefox webbrowser. It allows you to control devices in your home, log their data, and create home automations. It has an easy to user interface.
https://github.com/mozilla-iot/gateway

This adapter is built on top of the pyMySensors library by Theo Lind. This great library does the heavy lifting, and turns messages from the network into an easy to use stream of updates. This adapter turns that stream of messags into devices in the gateway.
https://github.com/theolind/pymysensors

It was created as part of the Candle project, which aims to create a prototype of a smart home that is much more privacy friendly that existing solutions. It's goal is to show that you can have a home that is both smart and privacy friendly.
https://www.createcandle.com



# Status
It currently supports most sensor inputs, as well as most actuators.

Missing or just partially implemented are:
- IR sender/receiver


Version 0.0.2 added the ability to select different radio gateways (serial, ethernet, MQTT), and had some improvements to property support.

Version 0.0.3 adds persistence, in the sense that handed out node ID's are remembered.

Version 0.0.4 makes persistance selectable, and adds the ability to send a discover command to all nodes so that they re-present themselves. This is done at start and when the user clicks on the (+) button. It also improves the temperature property's presentation.

Version 0.0.5 improves type support, implements smarter device removal, makes persistance work as you'd expect (recreates nodes as soon the gateway is restarted), and better implements capabilities support from the Mozilla IoT schema.

Version 0.0.6 added a debug option.

Version 0.0.7 fixed an issue where prefered capability to be centrally displayed was forgotton when the add-on restarted. Also removes the persistence option, and replaces it with the option to show a device as connected only after receiving a signal from it.

Version 0.0.8 made reading the configuration more robust, but introduced a bug.

Version 0.0.9 removed that bug, and then turned into:

Version 0.1.0 rewrote how persistence works in an attempt to fix an issue a user was having.

Version 0.1.1 tried to anticipate small changes in the upcoming version (0.9) of the WebThings gateway.

Version 0.1.2 added 
- Automatic serial port searching. User doesn't need to add a serial port ID manually anymore (but can if they want)
- Support for metric/imperial units. You can set your preference in the add-on settings.
- Support for multipleOf. This should help show a sane amount of decimals on numeric variables.
- Experimental MQTT support based on user feedback
- Anticipates switch to version 0.9 of the WebThings gateway by implementing title support.

Version 0.1.3 added
- New "optimize things" feature. This is a solution for things with a lot of OnOfProperty children. It basically clones them into new things. This makes the thing overview better able to function as a dashboard, and allows users to change the name for the properties. This is very useful for voice control.
- Slightly improved support for MySensors devices
- Attempts to use a different way of downloading requirements.

Version 1.0.0
- Support for timeout functionality. If a node doesn't respond withith a (user definable) timeframe, the node will set to disconnected.
- Fixed bug in HVAC support that meant not all V_types were properly supported.
- Support for thermostat capability of WebThings Gateway
-  Support for new Lock capability has purposefully been held back for now.


Version 1.0.3
- Attempt to make MQTT work (something I don't use myself, so anyone willing to help is welcome to)
