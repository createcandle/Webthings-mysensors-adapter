"""MySensors adapter for Mozilla WebThings Gateway."""

import time
import asyncio
import logging
import mysensors.mysensors as mysensors


from threading import Timer
from gateway_addon import Adapter, Database
from .mysensors_device import MySensorsDevice
from .util import pretty, is_a_number, get_int_or_float

_TIMEOUT = 3





class MySensorsAdapter(Adapter):
    """Adapter for MySensors"""

    def __init__(self, verbose=True):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
        self.adding_via_timer = False
        self.pairing = False
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'mysensors-adapter', 'mysensors-adapter', verbose=verbose)
        print("adapter ID = " + self.get_id())
        
        # This is the non-ASynchronous version, which is no longer used:
        #self.GATEWAY = mysensors.AsyncSerialGateway('/dev/ttyUSB0', baud=115200, timeout=1.0, reconnect_timeout=10.0, event_callback=self.event, persistence=False, persistence_file='./mysensors.pickle', protocol_version='2.2')
        ##self.GATEWAY.start_persistence()
        #self.GATEWAY.start()
        
        # This is the new asynchronous version of PyMySensors:
        self.LOOP = asyncio.get_event_loop()
        self.LOOP.set_debug(False)
        logging.basicConfig(level=logging.DEBUG)

        
        # Establishing a serial gateway:
        try:
            self.GATEWAY = mysensors.AsyncSerialGateway(
                '/dev/ttyUSB0', loop=self.LOOP, event_callback=self.event, 
                #persistence=True, persistence_file='./mysensors.json', 
                protocol_version='2.2')
            #self.GATEWAY.start_persistence() # uncomment to enable persistence.
            self.LOOP.run_until_complete(self.GATEWAY.start())
            self.LOOP.run_forever()
        except KeyboardInterrupt:
            print("keyboard interrupt")
            this.GATEWAY.stop()
            this.LOOP.close()
        except Exception as exc:  # pylint: disable=broad-except
            print(exc)


    def unload(self):
        print("Shutting down adapter")
        this.GATEWAY.stop()
        this.LOOP.close()


    def event(self, message):
        
        typeName = ''
        if message.type == 0:
            typeName = 'presentation'
        
        if message.type == 1:
            typeName = 'set'
        
        if message.type == 2:
            typeName = 'request'
            
        if message.type == 3:
            typeName = 'internal'
            
        if message.type == 4:
            typeName = 'stream'
            
        print()
        print(">> message > " + typeName + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))

        if message.node_id != 0 and message.ack == 0: # Ignore the gateway itself. It should not be presented as a device.
            
            # first we check if the incoming node_id already has a corresponding device
            try:
                targetDevice = self.get_device(str(message.node_id))
            except Exception as ex:
                print("Error while checking if node exists as device: " + str(ex))


            # PRESENTATION
            # Some properties can be added early because they have a predictable sub_type. Their S_type (which is available here) can be transformed into a V_type.
            if message.type == 0: # A presentation message
                print("PRESENTATION MESSAGE")
                
                # TODO: somehow check if there is already a property/value on the gateway. Update: apparently that is not possible.
                
                if str(targetDevice) != 'None':
                    
                    # The code below allows presentation messages to already create a property, even though the V_Type has not be received yet. It speeds up property creation, but can only be done if an S_ type only has one possible V_ type associated with it. See the MySensors serial api for details.
                    alt_sub_type = 0
                    alt_payload = ''
                    
                    if message.sub_type == 19:        # S_LOCK type
                        alt_sub_type = 36             # V_LOCK_STATUS
                        alt_payload = '0'               # We also modify the payload
                    
                    if message.sub_type == 36:        # S_INFO type
                        alt_sub_type = 47             # V_TEXT
                    
                    
                    # If we detect a modification, then we can try to create the property early.
                    if alt_sub_type != 0:
                        try:
                            targetDevice.add_child(self.GATEWAY.sensors[message.node_id].children[message.child_id], message, alt_sub_type, alt_payload)
                        except Exception as ex:
                            print("-Failed to add new device early from presentation:" + str(ex))
                else:
                    print("-Presented device did not exist in the gateway yet.")
                    try:
                        self._add_device(self.GATEWAY.sensors[message.node_id])
                    except Exception as ex:
                        print("-Failed to add new device from presentation message:" + str(ex))


            # INTERNAL
            # If the node is presented on the network and we get a name for it, then we can initiate a device object for it, if need be.
            if message.type == 3 and message.child_id != 255: # An internal message
                if message.sub_type == 11: # holds the name of the new device
                    if str(targetDevice) == 'None':
                        print("-Internally presented device did not exist in the gateway yet, let's try adding it.")
                            
                        try:
                            self._add_device(self.GATEWAY.sensors[message.node_id])
                        except Exception as ex:
                            print("-Failed to add new device:" + str(ex))
                        
                    else:
                        alt_sub_type = 0
                        alt_payload = ''

                        if message.sub_type == 19:        # S_LOCK type
                            alt_sub_type = 36             # V_LOCK_STATUS
                            alt_payload = '0'               # We also modify the payload

                        if message.sub_type == 36:        # S_INFO type
                            alt_sub_type = 47             # V_TEXT

                        # if we detect a modification, then we can try to create the property.
                        if alt_sub_type != 0:
                            try:
                                targetDevice.add_child(self.GATEWAY.sensors[message.node_id].children[message.child_id], message, alt_sub_type, alt_payload)
                            except Exception as ex:
                                print("-Failed to add new device from internal message:" + str(ex))
                else:
                    print("-Internally presented device did not exist in the gateway yet.")
                    try:
                        self._add_device(self.GATEWAY.sensors[message.node_id])
                    except Exception as ex:
                        print("-Failed to add new device from internal message:" + str(ex))


            #SET
            # The message is a 'set' message. This should update a property value or, if the property doesn't exist yet, create it.
            if message.type == 1:

                if str(targetDevice) != 'None': # if the device for this node already exists
                    #print("targetDevice = " + str(targetDevice))
                    if message.sub_type != 43: # avoid creating a property for V_UNIT_PREFIX
                        try:
                            targetPropertyID = str(message.node_id) + "-" + str(message.child_id) + "-" + str(message.sub_type) # e.g. 2-5-36
                            targetProperty = targetDevice.find_property(targetPropertyID)
                            #print("targetProperty = " + str(targetProperty))

                            # The property does not exist yet:
                            if str(targetProperty) == 'None': 
                                #print("property existence check gave None")
                                try:
                                    child = self.GATEWAY.sensors[message.node_id].children[message.child_id]
                                    print("-The PyMySensors node existed. Now to add it. " + str(child))
                                    targetDevice.add_child(child, message, message.sub_type, message.payload)
                                    print("-Finished proces of adding new property")
                                except Exception as ex:
                                    print("-Error adding property: " + str(ex))
                                
                            # The property has already been created, so update its value.    
                            else: 
                                print("-About to update: " + str(targetPropertyID))
                                try:
                                    if is_a_number(message.payload):
                                        new_value = get_int_or_float(message.payload)
                                    else:
                                        new_value = str(message.payload)
                                    
                                    print("New update value:" + str(new_value))
                                    targetProperty = targetDevice.find_property(targetPropertyID)
                                    #print("Target property object: " + str(targetProperty))
                                    targetProperty.set_cached_value(new_value)
                                    targetDevice.notify_property_changed(targetProperty)
                                    print("-Adapter has updated the property")
                                except Exception as ex:
                                    print("Update property error: " + str(ex))

                        except Exception as ex:
                            print("Error while handling 'set' message type: " + str(ex))

                # Not even the device has been created yet.
                else:
                    #print("Device doesn't exist (yet), so cannot update property.")
                    try:
                        self._add_device(self.GATEWAY.sensors[message.node_id])
                    except Exception as ex:
                        print("-Failed to add new device:" + str(ex))
            
            
            #REQUEST
            # This is a message that requests a value from the gateway.
            if message.type == 2: # A request message
                print(")()()(REQUEST")
                if str(targetDevice) != 'None':
                    print("-Will try to get existing value from Gateway.")
                    try:
                        targetPropertyID = str(message.node_id) + "-" + str(message.child_id) + "-" + str(message.sub_type) # e.g. 2-5-36
                        
                        requestResult = targetDevice.get_property(targetPropertyID)
                        print("-Request result: " + str(requestResult))
                        self.GATEWAY.set_child_value(message.node_id, message.child_id, message.sub_type, requestResult)
                        
                    except Exception as ex:
                        print("-Request for property value failed: " + str(ex))
                else:
                    print("Got a request for a device/property that did not exist (yet).")
                    # It would be possible to start the device/property creation proces here too.
                    

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.

        timeout -- Timeout in seconds at which to quit pairing
        """
        print()
        print("PAIRING INITIATED")
        
        if self.pairing:
            print("-Already pairing")
            return

        self.pairing = True
    

        
    def _add_device(self, node):
        """
        Add the given device, if necessary.

        dev -- the device object from pyMySensors
        """
        print("inside add device function @ adapter")
        try:
            if str(node.sketch_name) == 'None':
                print("-No sketch name yet, not adding devive.")
                return
        except Exception as ex:
            print("-Cannot add device: error checking sketch name:" + str(ex))
            return
        
        print()
        print("+ADDING DEVICE: " + str(node.sketch_name))
        device = MySensorsDevice(self, node.sensor_id, node)
        self.handle_device_added(device)
        print("-Adapter has finished adding new device")
        return


    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
 