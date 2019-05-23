"""MySensors adapter for Mozilla WebThings Gateway."""

import os
import time
import asyncio
import logging
import threading

import mysensors.mysensors as mysensors

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
        
        self.DEBUG = False
        
        self.first_request_done = False
        self.persist = False
        #self.persistence_file_path = './mysensors-adapter-persistence.json'
        self.add_from_config()
        
        
    def recreate_from_persistence(self):
        if self.persist:
            print("RECREATING DEVICES FROM PERSISTENCE")
            for nodeIndex in self.GATEWAY.sensors:
                if nodeIndex != 0:
                    try:
                        #print("Adding from persistence file = " + str(nodeIndex))
                        #newNodeObject = self.GATEWAY.sensors[message.node_id]
                        #print("new Node object = " + str(self.GATEWAY.sensors[nodeIndex]))
                        #print("new Node object sensor ID = " + str(self.GATEWAY.sensors[nodeIndex].sensor_id))


                        if str(self.GATEWAY.sensors[nodeIndex].sketch_name) == 'None':
                            name = 'MySensors_' + str(nodeIndex)
                            #name = 'MySensors_{}'.format(nodeIndex)
                            if self.DEBUG:
                                print("-Node was in persistence, but no sketch name was found.")
                        else:
                            name = str(self.GATEWAY.sensors[nodeIndex].sketch_name)

                        print("-Recreating: " + name)
                        device = MySensorsDevice(self, nodeIndex, name)
                        self.handle_device_added(device)

                        #print(str(self.GATEWAY.sensors[nodeIndex]))
                        if self.GATEWAY.sensors[nodeIndex].children:
                            for childIndex in self.GATEWAY.sensors[nodeIndex].children:
                                child = self.GATEWAY.sensors[nodeIndex].children[childIndex]

                                if child.values:
                                    for valueIndex in child.values:
                                        if valueIndex != 43: #Avoid V_UNIT_PREFIX
                                            device.add_child(child, nodeIndex, childIndex, valueIndex, child.values[valueIndex])

                    except Exception as ex:
                        print("Error during recreation from persistence file: " + str(ex))


        
        
        
    def start_pymysensors_gateway(self, selected_gateway_type, dev_port='/dev/ttyUSB0', ip_address='127.0.0.1'):
        # This is the non-ASynchronous version, which is no longer used:
        #self.GATEWAY = mysensors.AsyncSerialGateway('/dev/ttyUSB0', baud=115200, timeout=1.0, reconnect_timeout=10.0, event_callback=self.event, persistence=False, persistence_file='./mysensors.pickle', protocol_version='2.2')
        #self.GATEWAY.start_persistence()
        #self.GATEWAY.start()
        
        # This is the new asynchronous version of PyMySensors:
        self.LOOP = asyncio.get_event_loop()
        self.LOOP.set_debug(False)
        
        if self.DEBUG:
            logging.basicConfig(level=logging.DEBUG)
        else:
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
            
            #if self.persist:
            self.LOOP.run_until_complete(self.GATEWAY.start_persistence()) # comment this line to disable persistence. Persistence means the add-on keeps its own list of mysensors devices.
            
            self.LOOP.run_until_complete(self.GATEWAY.start())
            self.LOOP.run_forever()
        except Exception as ex:  # pylint: disable=broad-except
            print("Unable to initialise the PyMySensors object. Error: " + str(ex))    



    def unload(self):
        print("Shutting down MySensors adapter")
        try:
            self.GATEWAY.stop()
            self.LOOP.close()
        except:
            print("MySensors adapter was unable to cleanly close PyMySensors")


    def remove_thing(self, device_id):
        if self.DEBUG:
            print("-----REMOVING------")
        
        try:
            ID_to_clear = int(device_id.split('_')[-1])
            if self.DEBUG:
                print("THING TO REMOVE ID:" + str(device_id))
                print("THING TO REMOVE IN DEVICES DICT:" + str(self.devices[device_id]))

            del self.GATEWAY.sensors[ID_to_clear]    
            obj = self.get_device(device_id)
            self.handle_device_removed(obj)
            print("Removed MySensors_" + str(ID_to_clear))
        except:
            print("REMOVING MYSENSORS THING FAILED")

        


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

            if self.DEBUG:
                print(">> message > " + typeName + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))

        except:
            print("Error while displaying message in console")
        
        try:
            if message.node_id == 0: # and message.ack == 0: # Ignore the gateway itself. It should not be presented as a device.
                if message.sub_type == 18 and self.first_request_done == False:
                    
                    if self.persist:
                        self.recreate_from_persistence() # Recreate everything from the persistence file.
                    
                    self.first_request_done = True
                    self.t = threading.Thread(target=self.rerequest)
                    self.t.daemon = True
                    self.t.start()
                    
                
            else:
                # first we check if the incoming node_id already has a corresponding device
                try:
                    targetDevice = self.get_device("MySensors_" + str(message.node_id))
                except Exception as ex:
                    print("Error while checking if node exists as device: " + str(ex))
                    
                    
                # INTERNAL
                # If the node is presented on the network and we get a name for it, then we can initiate a device object for it, if need be.
                if message.type == 3: #and message.child_id != 255: # An internal message
                    if message.sub_type == 11: # holds the sketch name, which will be the name of the new device
                        if str(targetDevice) == 'None':
                            #print("-Internally presented device did not exist in the gateway yet. Adding now.")

                            try:
                                device = MySensorsDevice(self, message.node_id, str(message.payload))
                                self.handle_device_added(device)

                            except Exception as ex:
                                print("-Failed to add new device from internal presentation: " + str(ex))


                #SET
                # The message is a 'set' message. This should update a property value or, if the property doesn't exist yet, create it.
                elif message.type == 1:

                    if str(targetDevice) != 'None': # if the device for this node already exists
                        #print("targetDevice = " + str(targetDevice))
                        if message.sub_type != 43: # avoid creating a property for V_UNIT_PREFIX
                            try:
                                targetPropertyID = str(message.node_id) + "-" + str(message.child_id) + "-" + str(message.sub_type) # e.g. 2-5-36
                                targetProperty = targetDevice.find_property(targetPropertyID)
                                #if self.DEBUG:
                                    #print("adapter; targetProperty = " + str(targetProperty))

                                # The property does not exist yet:
                                if str(targetProperty) == 'None': 
                                    if self.DEBUG:
                                        print("property existence check gave None")
                                    try:
                                        child = self.GATEWAY.sensors[message.node_id].children[message.child_id]
                                        print("-The PyMySensors node existed. Now to add it. Child = " + str(child))
                                        targetDevice.add_child(child, message.node_id, message.child_id, message.sub_type, message.payload)
                                        print("-Finished proces of adding new property")
                                    except Exception as ex:
                                        if self.DEBUG:
                                            print("-Error adding property: " + str(ex))
                                        #if self.persist:
                                        del self.GATEWAY.sensors[message.node_id].children[message.child_id] # Maybe delete the entire node? Start fresh?
                                        print("Removed faulty child from gateway object")
                                        

                                # The property has already been created, so update its value.    
                                else: 
                                    if self.DEBUG:
                                        #pass
                                        print("-About to update: " + str(targetPropertyID))
                                    
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
                        if self.DEBUG:
                            print("Device doesn't exist (yet), so cannot update property. Will try to create the device now using persistence data.")
                        
                        if message.node_id in self.GATEWAY.sensors:
                            try:
                                if str(self.GATEWAY.sensors[message.node_id].sketch_name) == 'None':
                                    name = 'MySensors_' + str(message.node_id)
                                    if self.DEBUG:
                                        print("-Node was in persistence, but no sketch name found.")
                                else:
                                    name = str(self.GATEWAY.sensors[message.node_id].sketch_name)
                                
                                print("name for the new device is: " + name)
                                device = MySensorsDevice(self, message.node_id, name)
                                self.handle_device_added(device)
                            except Exception as ex:
                                print("-Failed to add new device from internal presentation: " + str(ex))
                        else:
                            print("Node ID not found in persistence file, so cannot re-create device. Please restart the node.")

        except Exception as ex:
            print("-Failed to handle message:" + str(ex))


    def rerequest(self):

        if self.DEBUG:
            print("Re-requesting presentation of all nodes on the network")
        try:
            #if not self.persist:
            self.GATEWAY.send('0;255;3;0;26;0\n') # Ask all nodes within earshot to respond with their node ID's.
                
            # this asks all known devices to re-present themselves. IN a future version this request could only be made to nodes where a device property count is lower than expected.
            for index in self.GATEWAY.sensors: #, sensor
                if index != 0:
                    if self.DEBUG:
                        print("<< Requesting presentation from " + str(index))
                    discover_encoded_message = str(index) + ';255;3;0;19;\n'
                    self.GATEWAY.send(discover_encoded_message)
                    time.sleep(1)
                    
        except:
            print("error while manually re-requesting presentations")
            


    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.

        timeout -- Timeout in seconds at which to quit pairing
        """
        #print()
        if self.DEBUG:
            print("PAIRING INITIATED")
        
        if self.pairing:
            print("-Already pairing")
            return

        self.pairing = True
        
        # re-request that all nodes present themselves.
        if not self.t.is_alive():
            self.t = threading.Thread(target=self.rerequest)
            self.t.daemon = True
            self.t.start()
        else:
            if self.DEBUG:
                print("ALREADY REQUESTING PRESENTATIONS FROM NODES")
        
        return


    def add_from_config(self):
        """Attempt to add all configured devices."""
        database = Database('mysensors-adapter')
        if not database.open():
            return

        config = database.load_config()
        database.close()

        if not config or 'Gateway' not in config:
            return

        if 'Persistence' not in config:
            return
        
        self.persist = config['Persistence']
        
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
        
        print("-loaded config")
        return


    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
        
        '''
        if self.DEBUG:
            print("Starting pruning")
        # Prune empty devices from the list
        try:
            empty_node_list = []
            for nodeID in self.GATEWAY.sensors:
                if nodeID != 0 and not any(self.GATEWAY.sensors[nodeID].children):
                    if self.DEBUG:
                        print("Pruning node with ID " + str(nodeID))
                    empty_node_list.append(nodeID)

            for nodeID in empty_node_list:
                del self.GATEWAY.sensors[nodeID]
            
            if self.DEBUG:
                print("Finished pruning")
        
        except:
            print("Error while pruning")
        '''

 