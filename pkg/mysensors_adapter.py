"""MySensors adapter for Mozilla WebThings Gateway."""

import os
import time
import asyncio
import logging
import mysensors.mysensors as mysensors


from threading import Timer
from gateway_addon import Adapter, Database
from .mysensors_device import MySensorsDevice
from .util import pretty, is_a_number, get_int_or_float

_TIMEOUT = 3

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))



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
        #print("Adapter ID = " + self.get_id())
        
        for path in _CONFIG_PATHS:
            if os.path.isdir(path):
                self.persistence_file_path = os.path.join(
                    path,
                    'mysensors-adapter-persistence.json'
                )
        
        self.add_from_config()



    def start_pymysensors_gateway(self, selected_gateway_type, dev_port='/dev/ttyUSB0', ip_address='127.0.0.1'):
        # This is the non-ASynchronous version, which is no longer used:
        #self.GATEWAY = mysensors.AsyncSerialGateway('/dev/ttyUSB0', baud=115200, timeout=1.0, reconnect_timeout=10.0, event_callback=self.event, persistence=False, persistence_file='./mysensors.pickle', protocol_version='2.2')
        ##self.GATEWAY.start_persistence()
        #self.GATEWAY.start()
        
        # This is the new asynchronous version of PyMySensors:
        self.LOOP = asyncio.get_event_loop()
        self.LOOP.set_debug(False)
        
        #logging.basicConfig(level=logging.DEBUG)
        logging.basicConfig(level=logging.INFO)
        
        # Establishing a serial gateway:
        try:
            if selected_gateway_type == 'USB Serial gateway':
                self.GATEWAY = mysensors.AsyncSerialGateway(
                    dev_port, loop=self.LOOP, event_callback=self.mysensors_message, 
                    persistence=True, persistence_file=self.persistence_file_path, 
                    protocol_version='2.2')
                
            
            elif selected_gateway_type == 'Ethernet gateway':
                self.GATEWAY = mysensors.AsyncTCPGateway(ip_address, event_callback=self.mysensors_message, 
                    persistence=True, persistence_file=self.persistence_file_path, 
                    protocol_version='2.2')

            elif selected_gateway_type == 'MQTT gateway':
                self.GATEWAY = mysensors.AsyncMQTTGateway(ip_address, event_callback=self.mysensors_message, 
                    persistence=True, persistence_file=self.persistence_file_path, 
                    protocol_version='2.2')
            
            self.LOOP.run_until_complete(self.GATEWAY.start_persistence()) # comment this line to disable persistence. Persistence means the add-on keeps its own list of mysensors devices.
            
            self.LOOP.run_until_complete(self.GATEWAY.start())
            self.LOOP.run_forever()
        except Exception as exc:  # pylint: disable=broad-except
            print(exc)



    def unload(self):
        print("Shutting down adapter")
        self.GATEWAY.stop()
        self.LOOP.close()



    def mysensors_message(self, message):
        try:
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

            #print()
            #print(">> message > " + typeName + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))

        except:
            print("Error while displaying message in console")
        
        try:
            if message.node_id != 0 and message.ack == 0: # Ignore the gateway itself. It should not be presented as a device.

                # first we check if the incoming node_id already has a corresponding device
                try:
                    targetDevice = self.get_device("MySensors_" + str(message.node_id))
                except Exception as ex:
                    print("Error while checking if node exists as device: " + str(ex))


                # PRESENTATION
                # Some properties can be added early because they have a predictable sub_type. Their S_type (which is available here) can be transformed into a V_type.
                if message.type == 0: # A presentation message
                    #print("PRESENTATION MESSAGE")

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

                        if message.sub_type == 38:        # S_GPS type
                            alt_sub_type = 49             # V_POSITION

                        # If we detect a modification, then we can try to create the property early.
                        if alt_sub_type != 0:
                            try:
                                targetDevice.add_child(self.GATEWAY.sensors[message.node_id].children[message.child_id], message, alt_sub_type, alt_payload)
                            except Exception as ex:
                                print("-Failed to add new device early from presentation:" + str(ex))
                    else:
                        print("-Presented device did not exist in the gateway yet. Adding now.")
                        try:
                            self._add_device(self.GATEWAY.sensors[message.node_id])
                        except Exception as ex:
                            print("-Failed to add new device from presentation message:" + str(ex))
                            
                            
            # INTERNAL
            # If the node is presented on the network and we get a name for it, then we can initiate a device object for it, if need be.
            if message.type == 3 and message.child_id != 255: # An internal message
                if message.sub_type == 11: # holds the name of the new device
                    if str(targetDevice) == 'None':
                        #print("-Internally presented device did not exist in the gateway yet. Adding now.")
                            
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
                    #print("-Internally presented device did not exist in the gateway yet.")
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
                                    #print("-The PyMySensors node existed. Now to add it. " + str(child))
                                    targetDevice.add_child(child, message, message.sub_type, message.payload)
                                    #print("-Finished proces of adding new property")
                                except Exception as ex:
                                    print("-Error adding property: " + str(ex))
                                
                            # The property has already been created, so update its value.    
                            else: 
                                #print("-About to update: " + str(targetPropertyID))
                                try:
                                    if is_a_number(message.payload):
                                        new_value = get_int_or_float(message.payload)
                                    else:
                                        new_value = str(message.payload)
                                    
                                    #print("New update value:" + str(new_value))
                                    targetProperty = targetDevice.find_property(targetPropertyID)
                                    #print("Target property object: " + str(targetProperty))
                                    targetProperty.set_cached_value(new_value)
                                    targetDevice.notify_property_changed(targetProperty)
                                    #print("-Adapter has updated the property")
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
        except Exception as ex:
            print("-Failed to add new device:" + str(ex))



    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.

        timeout -- Timeout in seconds at which to quit pairing
        """
        #print()
        #print("PAIRING INITIATED")
        
        if self.pairing:
            print("-Already pairing")
            return

        self.pairing = True

        # Use this opportunity to manually re-request a presentation from all nodes?
        #try:
        #    for index, sensor in self.GATEWAY.sensors: # The values dictionary can contain multiple items. We loop over each one.
        #        print(str(sensor.sensor_id))
        #        
        #    #This is what a re-request presentation message looks like: 10;255;3;0;6;3
        #        
        #    request_presentation_message = Message
        #    
        #    
        #        
        #    self.GATEWAY.send(request_presentation_message)
        #    
        #except:
        #    print("Weird: error while looking for a prefix")

        #I_PRESENTATION = 19
        #self.GATEWAY.sensors[message.node_id].sensor_id
        #self.GATEWAY.set_child_value(message.node_id, message.child_id, message.sub_type, requestResult)



    def add_from_config(self):
        """Attempt to add all configured devices."""
        database = Database('mysensors-adapter')
        if not database.open():
            return

        config = database.load_config()
        database.close()

        if not config or 'Gateway' not in config:
            return

        selected_gateway_type = str(config['Gateway'])
        
        if config['Gateway'] == 'USB Serial gateway':
            print("Selected: USB Serial gateway")
            
            if 'USB device name' not in config:
                dev_port = '/dev/ttyUSB0'
            elif str(config['USB device name']) == '':
                dev_port = '/dev/ttyUSB0'
            else:
                dev_port = str(config['USB device name'])
            
            self.start_pymysensors_gateway(selected_gateway_type, dev_port, '')
        
        elif config['Gateway'] == 'Ethernet gateway':
            print("Selected: Ethernet gateway")
            
            if 'IP address' not in config:
                ip_address = '127.0.0.1'
            elif str(config['IP address']) == '':
                ip_address = '127.0.0.1'
            else:
                ip_address = str(config['IP address'])
            
            self.start_pymysensors_gateway(selected_gateway_type, '', ip_address)
            
        elif config['Gateway'] == 'MQTT gateway':
            print("Selected: MQTT gateway")
            
            if 'IP address' not in config:
                ip_address = '127.0.0.1'
            elif str(config['IP address']) == '':
                ip_address = '127.0.0.1'
            else:
                ip_address = str(config['IP address'])
            
            self.start_pymysensors_gateway(selected_gateway_type, '', ip_address)
            
        
        #print(str(config['Ethernet address']))
        
        #for address in config['addresses']:
        #    try:
        #        dev = Discover.discover_single(address)
        #    except (OSError, UnboundLocalError) as e:
        #        print('Failed to connect to {}: {}'.format(address, e))
        #        continue

        #    if dev:
        #        self._add_device(dev)



    def _add_device(self, node):
        """
        Add the given device, if necessary.

        node -- the object from pyMySensors
        """
        #print("inside add device function @ adapter")
        try:
            if str(node.sketch_name) == 'None':
                print("-No sketch name yet. Cancalling adding device.")
                return
        except Exception as ex:
            print("-Cannot add device: error checking sketch name:" + str(ex))
            return
        
        #print()
        print("+ADDING DEVICE: " + str(node.sketch_name))
        device = MySensorsDevice(self, node.sensor_id, node)
        self.handle_device_added(device)
        #print("-Adapter has finished adding new device")
        return



    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
 