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
        self.show_connection_status = True
        self.first_request_done = False
        
        self.t = threading.Thread(target=self.rerequest)
        self.t.daemon = True
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config (and initialising PyMySensors library?): " + str(ex))


    def recreate_from_persistence(self):
        print("RECREATING DEVICES FROM PERSISTENCE")
        try:
            for nodeIndex in self.GATEWAY.sensors:
                if nodeIndex != 0:
                    try:
                        #print("Adding from persistence file = " + str(nodeIndex))
                        #newNodeObject = self.GATEWAY.sensors[message.node_id]
                        #print("new Node object = " + str(self.GATEWAY.sensors[nodeIndex]))
                        #print("new Node object sensor ID = " + str(self.GATEWAY.sensors[nodeIndex].sensor_id))
                        
                        name = "nameless"
                        # Come up with a name for the device
                        if str(self.GATEWAY.sensors[nodeIndex].sketch_name) == 'None':
                            name = 'MySensors_' + str(nodeIndex)
                            #name = 'MySensors_{}'.format(nodeIndex)
                            if self.DEBUG:
                                print("-Node was in persistence, but no sketch name was found.")
                        else:
                            name = str(self.GATEWAY.sensors[nodeIndex].sketch_name)
                        if self.DEBUG:
                            print("")
                        print("-Recreating: " + name)
                        
                        # We create the device object
                        device = MySensorsDevice(self, nodeIndex, name)
                        
                        # We add all the children to it as properties
                        if self.GATEWAY.sensors[nodeIndex].children:
                            for childIndex in self.GATEWAY.sensors[nodeIndex].children:
                                child = self.GATEWAY.sensors[nodeIndex].children[childIndex]
                                
                                if child.values:
                                    for valueIndex in child.values:
                                        if valueIndex != 43: #Avoid V_UNIT_PREFIX
                                            device.add_child(child, nodeIndex, childIndex, valueIndex, child.values[valueIndex])
                                            
                        # Finally, now that the device is complete, we present it to the Gateway.
                        self.handle_device_added(device)
                        
                    except Exception as ex:
                        print("Error during recreation of thing from persistence: " + str(ex))
                        
                    # Optionally, set the initial connection status to 'not connected'.
                    if self.show_connection_status:
                        try:
                            # Create a handle to the new device, and use its notify function.
                            targetDevice = self.get_device("MySensors_" + str(nodeIndex))
                            if targetDevice != 'None':
                                targetDevice.connected_notify(False)
                                if self.DEBUG:
                                    print("-Seting intial device status to not connected.")
                        except Exception as ex:
                            print("Failed to set initial connection status to false: " + str(ex))

        except Exception as ex:
            print("Error during recreation from persistence: " + str(ex))


   

        
        
        
    def start_pymysensors_gateway(self, selected_gateway_type, dev_port='/dev/ttyUSB0', ip_address='127.0.0.1:5003'):
        # This is the non-ASynchronous version, which is no longer used:
        #self.GATEWAY = mysensors.AsyncSerialGateway('/dev/ttyUSB0', baud=115200, timeout=1.0, reconnect_timeout=10.0, event_callback=self.event, persistence=False, persistence_file='./mysensors.pickle', protocol_version='2.2')
        #self.GATEWAY.start_persistence()
        #self.GATEWAY.start()
        
        # This is the new asynchronous version of PyMySensors:
        try:
            self.LOOP = asyncio.get_event_loop()
            self.LOOP.set_debug(False)
        except:
            print("Error getting asyncio event loop!")
        
        if self.DEBUG:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        # Establishing a MySensors gateway:
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
            
            self.LOOP.run_until_complete(self.GATEWAY.start_persistence())
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
            print("MySensors adapter was unable to cleanly close PyMySensors. This is not a problem.")


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
        # Show some human readable details about the incoming message
        try:
            if self.DEBUG:
                type_names = ['presentation','set','request','internal','stream']
                print(">> incoming message > " + str(type_names[message.type]) + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))
        except:
            print("Error while displaying incoming message in console.")
        
        
        
        # When the first message arrives, try to re-create things from persistence, and then ask all nodes to present themselves.
        try:
            if self.first_request_done == False:
                self.first_request_done = True
                try:
                    self.recreate_from_persistence() # Recreate everything from the persistence file.
                except Exception as ex:
                    print("Error while initiating recreate_from_persistence: " + str(ex))
                try:
                    self.try_rerequest() # Aks all nodes to present themselves
                except Exception as ex:
                    print("Error while initiating re-request of nodes: " + str(ex))
        except:
            print("Error dealing with first incoming message")
        
        
        # Handle the incoming message
        try:
            # If the messages is coming from a device in the MySensors network:
            if message.node_id != 0:
                # first we check if the incoming node_id already has already been presented to the WebThings Gateway.
                try:
                    targetDevice = self.get_device("MySensors_" + str(message.node_id)) # targetDevice will be 'None' if it wasn't found.
                except Exception as ex:
                    print("Error while checking if node exists as device: " + str(ex))
                    
                    
                # INTERNAL
                # If the node is presented on the network and we get a name for it, then we can initiate a device object for it, if need be.
                if message.type == 3: #and message.child_id != 255: # An internal message
                    if str(targetDevice) == 'None':
                        if message.sub_type == 11: # holds the sketch name, which will be the name of the new device
                            if self.DEBUG:
                                print("-Internally presented device did not exist in the gateway yet. Adding now.")

                            try:
                                device = MySensorsDevice(self, message.node_id, str(message.payload))
                                if self.DEBUG:
                                    self.handle_device_added(device) # This could be removed. Ideally it would only be called after at least one child pas presented itself. On the other hand, it could be useful to show that a device did respond, even if the children couldn't be properly processed.

                            except Exception as ex:
                                print("-Failed to add new device from internal presentation: " + str(ex))
                    else:
                        if targetDevice.connected == False:
                            targetDevice.connected = True
                            targetDevice.connected_notify(True)


                #SET
                # The message is a 'set' message. This should update a property value or, if the property doesn't exist yet, create it.
                elif message.type == 1:

                    # If there is a 'set' message but the device for this node somehow doesn't exist yet, then we should quickly create it.
                    if str(targetDevice) == 'None':
                        if self.DEBUG:
                            print("Incoming 'set' message, but device doesn't exist (yet). If possible, will try to quickly create the device using persistence data.") # Perhaps the persistence data can help. Not sure if this situtation is even possible now that persistence is always used.
                        if message.node_id in self.GATEWAY.sensors:
                            try:
                                if str(self.GATEWAY.sensors[message.node_id].sketch_name) == 'None':
                                    name = 'MySensors_' + str(message.node_id)
                                    if self.DEBUG:
                                        print("-Node was in persistence, but no sketch name found. Generated a generic name.")
                                else:
                                    name = str(self.GATEWAY.sensors[message.node_id].sketch_name)

                                print("-Name for the new device is: " + name)
                                device = MySensorsDevice(self, message.node_id, name)
                                self.handle_device_added(device)
                                
                                # Now try to get that device handle again.
                                try:
                                    targetDevice = self.get_device("MySensors_" + str(message.node_id)) # targetDevice will be 'None' if it wasn't found.
                                except Exception as ex:
                                    print("Error while checking if node exists as device AGAIN: " + str(ex))
                    
                            except Exception as ex:
                                print("-Failed to add new device: " + str(ex))
                        else:
                            print("Node ID not found in persistence file, so cannot re-create device. Please restart the node.")
                            
                        

                    if str(targetDevice) != 'None':
                        #print("targetDevice = " + str(targetDevice))
                        if message.sub_type != 43: # avoid creating a property for V_UNIT_PREFIX
                            try:
                                targetPropertyID = str(message.node_id) + "-" + str(message.child_id) + "-" + str(message.sub_type) # e.g. 2-5-36
                                targetProperty = targetDevice.find_property(targetPropertyID)
                                #if self.DEBUG:
                                    #print("adapter; targetProperty = " + str(targetProperty))
                            except Exception as ex:
                                print("Error getting target property: " + str(ex))

                            # The property does not exist yet:
                            if str(targetProperty) == 'None': 
                                if self.DEBUG:
                                    print("-Property did not exist yet.")
                                try:
                                    child = self.GATEWAY.sensors[message.node_id].children[message.child_id]
                                    if self.DEBUG:
                                        print("-The PyMySensors node existed, and has child data. Now to present it to the WebThings Gateway. Child = " + str(child))
                                    targetDevice.add_child(child, message.node_id, message.child_id, message.sub_type, message.payload)
                                    print("-Finished proces of adding new property on new device. Presenting it to the WebThings Gateway now.")
                                    self.handle_device_added(targetDevice)
                                    
                                    # Once the property has been created, we create a handle for it.
                                    targetProperty = targetDevice.find_property(targetPropertyID)
                                    #device.connected_notify(False)

                                except Exception as ex:
                                    if self.DEBUG:
                                        print("-Error adding property: " + str(ex))
                                    del self.GATEWAY.sensors[message.node_id].children[message.child_id] # Maybe delete the entire node? Start fresh?
                                    if self.DEBUG:
                                        print("-Removed faulty node child from persistence data")


                            # The property has already been created, so just update its value.    
                            if str(targetProperty) != 'None':
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
                                    targetProperty.update(new_value)
                                    #targetProperty.set_cached_value(new_value)
                                    #targetDevice.notify_property_changed(targetProperty)
                                    if self.DEBUG:
                                        print("-Adapter has updated the property")
                                except Exception as ex:
                                    print("Update property error: " + str(ex))

                        if targetDevice.connected == False:
                            targetDevice.connected = True
                            targetDevice.connected_notify(True)
                                    
        except Exception as ex:
            print("-Failed to handle message:" + str(ex))




    def try_rerequest(self):
        print("try_rerequest() called")
        # re-request that all nodes present themselves, but only is that thread isn't already running / doesn't already exist.
        try:
            self.t
        except NameError:
            try:
                self.t = threading.Thread(target=self.rerequest)
                self.t.daemon = True
                self.t.start()
                print("Re-request thread created")
            except:
                print("Could not create thread")
        else:
            try:
                if not self.t.is_alive():
                    # Restarting request for presentation of nodes
                    self.t = threading.Thread(target=self.rerequest)
                    self.t.daemon = True
                    self.t.start()
                    print("Re-request of node presentation restarted")
                else:
                    if self.DEBUG:
                        print("Already busy re-requesting nodes.")
            except:
                print("Error checking if re-request thread was alive")
            
            return


    def rerequest(self):
        print("rerequest() called")
        if self.DEBUG:
            print("Re-requesting presentation of all nodes on the network")
        try:
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
        
        return
            


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
        
        self.try_rerequest()
    
        return



    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database('mysensors-adapter')
            if not database.open():
                return

            config = database.load_config()
            database.close()
        except:
            print("Error! Failed to open settings database.")

        if not config:
            print("Error loading config from database")
            return
        
        # Fill the variables
        
        try:
            if 'Show connection status' in config:
                print("-Connection status was present in the config data.")
                self.show_connection_status = config['Show connection status']
            if 'Debugging' in config:
                self.DEBUG = config['Debugging']
            else:
                self.DEBUG = False
                
            if 'Gateway' in config:
                selected_gateway_type = str(config['Gateway'])
                print("-Gateway choice: " + selected_gateway_type)
            else:
                print("Error: no gateway type selected in add-on settings!")

            # Select the desired PyMySensors type
            if selected_gateway_type == 'USB Serial gateway':

                if 'USB device name' not in config or str(config['USB device name']) == '':
                    print("USB gateway selected, but no device name selected. Using default (/dev/ttyUSB0)")
                    dev_port = '/dev/ttyUSB0'
                else:
                    dev_port = str(config['USB device name'])

                if self.DEBUG:
                    print("Selected USB device address: " + str(dev_port))
                self.start_pymysensors_gateway(selected_gateway_type, dev_port, '')

            elif selected_gateway_type == 'Ethernet gateway':

                if 'IP address' not in config or str(config['IP address']) == '':
                    ip_address = '127.0.0.1:5003'
                else:
                    ip_address = str(config['IP address'])
                
                if self.DEBUG:
                    print("Selected IP address and port: " + str(ip_address))
                self.start_pymysensors_gateway(selected_gateway_type, '', ip_address)

            elif selected_gateway_type == 'MQTT gateway':

                if 'IP address' not in config or str(config['IP address']) == '':
                    ip_address = '127.0.0.1'
                else:
                    ip_address = str(config['IP address'])
                
                if self.DEBUG:
                    print("Selected IP address: " + str(ip_address))
                self.start_pymysensors_gateway(selected_gateway_type, '', ip_address)

            if self.DEBUG:
                print("MySensors add-on has succesfully loaded the configuration.")
        except Exception as ex:
            print("Error extracting settings from config object: " + str(ex))
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

 