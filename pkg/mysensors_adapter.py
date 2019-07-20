"""MySensors adapter for Mozilla WebThings Gateway."""

import os

import json
import asyncio
import logging
import threading

import serial
import serial.tools.list_ports as prtlst

import paho.mqtt.client as mqtt # pylint: disable=import-error
import mysensors.mysensors as mysensors

import time
from time import sleep

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
        
        self.metric = True
        self.temperature_unit = 'degree celsius'
        self.DEBUG = True
        self.show_connection_status = True
        self.first_request_done = False
        self.initial_serial_devices = set()
        
        self.MQTT_username = ""
        self.MQTT_password = ""
        
        try:
            print("Making initial scan of USB ports")
            self.scan_usb_ports()
        except:
            print("Error during initial scan of usb ports")
            
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config (and initialising PyMySensors library?): " + str(ex))



    def recreate_from_persistence(self):
        print("RECREATING DEVICES FROM PERSISTENCE")
        
        try:
            with open(self.persistence_file_path) as f:
                self.last_known_data = json.load(f)
                #print(str(self.last_known_data))
        except:
            print("Could not open persistence JSON file (if you just installed the add-on then this is normal)")
            return
        
        try:
            for nodeIndex in self.last_known_data:
                if self.DEBUG:
                    print("")
                    print("#" + str(nodeIndex))
                node = self.last_known_data[nodeIndex]
                #print("node object:" + str(node))
                if int(nodeIndex) != 0:
                    try:
                        if str(node['sketch_name']) == 'None':
                            name = 'MySensors_{}'.format(nodeIndex)
                            if self.DEBUG:
                                print("-Node was in persistence, but no sketch name was found.")
                        else:
                            name = str(node['sketch_name']) ##str(self.last_known_data[nodeIndex].sketch_name)
                            
                        if self.DEBUG:
                            print("")
                            print("-Recreating: " + str(name))
                        
                        # We create the device object
                        device = MySensorsDevice(self, nodeIndex, name)
                        
                        if node['children']:
                            for childIndex in node['children']:
                                child = node['children'][childIndex] #self.last_known_data[nodeIndex].children[childIndex]
                                #print("CHILD OBJECT: " + str(child))
                                if child['values']:
                                    for valueIndex in child['values']:
                                        #print("child['values'][" + str(valueIndex) + "] = " + str(child['values'][valueIndex]))
                                        if int(valueIndex) != 43: #Avoid V_UNIT_PREFIX
                                            device.add_child(child['description'], nodeIndex, childIndex, child['type'], valueIndex, child['values'], child['values'][valueIndex])
                                            
                        # Finally, now that the device is complete, we present it to the Gateway.
                        self.handle_device_added(device)
                        
                        # Optionally, set the initial connection status to 'not connected'.
                        try:
                            #print("self.show_connection_status = " + str(self.show_connection_status))
                            if self.show_connection_status == True:
                                print("Showing device as disconnected. It will be set to 'connected' as soon as it actually makes a connection.")
                                # Create a handle to the new device, and use its notify function.
                                targetDevice = self.get_device("MySensors_" + str(nodeIndex))
                                if str(targetDevice) != 'None':
                                    targetDevice.connected_notify(False)
                                    if self.DEBUG:
                                        print("-Setting initial device status to not connected.")
                            else:
                                print("Not changing connection status")
                        except Exception as ex:
                            print("Failed to set initial connection status to false: " + str(ex))






                    except Exception as ex:
                        print("Error during recreation of thing from persistence: " + str(ex))
                        


        except Exception as ex:
            print("Error during recreation from persistence: " + str(ex))

        print("End of recreation function")
        return




    def start_pymysensors_gateway(self, selected_gateway_type, dev_port='/dev/ttyUSB0', ip_address='127.0.0.1'):
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
        
        #if self.DEBUG:
        #    logging.basicConfig(level=logging.DEBUG)
        #else:
        #    logging.basicConfig(level=logging.INFO) # TODO try ERROR level?
        
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
                print("Starting MQTT version, connecting to port 1883 on IP address " + str(ip_address))
                try:
                    #print("MQTT Creating object")
                    self.MQTTC = MQTT(ip_address, 1883, 60)
                    
                    if self.MQTT_username != '' and self.MQTT_password != '':
                        self.MQTTC.username_pw_set(username=self.MQTT_username,password=self.MQTT_password)
                        print("-set MQTT username and password")
                    #print("MQTT will start")
                    self.MQTTC.start()
                except Exception as ex:
                    print("MQTT object error: " + str(ex))
                    
                
                #self.GATEWAY = mysensors.AsyncMQTTGateway(ip_address, event_callback=self.mysensors_message, 
                #    persistence=True, persistence_file=self.persistence_file_path, 
                #    protocol_version='2.2')
                
                try:
                    self.GATEWAY = mysensors.AsyncMQTTGateway(self.MQTTC.publish, self.MQTTC.subscribe, in_prefix='mygateway1-out',
                        out_prefix='mygateway1-in', retain=True, event_callback=self.mysensors_message,
                        persistence=True, persistence_file=self.persistence_file_path, 
                        protocol_version='2.2')
                except Exception as ex:
                    print("AsyncMQTTGateway object error: " + str(ex))
                
            try:
                self.LOOP.run_until_complete(self.GATEWAY.start_persistence())
                self.LOOP.run_until_complete(self.GATEWAY.start())    
                
                self.LOOP.run_forever()
            except:
                print("Asyncio loop is not running")
            
            
        except Exception as ex:  # pylint: disable=broad-except
            print("ERROR! Unable to initialise the PyMySensors object. Details: " + str(ex))    



    def unload(self):
        print("Shutting down MySensors adapter")
        
        try:
            self.GATEWAY.stop()
        except:
            print("MySensors adapter was unable to cleanly close PyMySensors object. This is not a problem.")
            
        try:
            for task in asyncio.Task.all_tasks():
                task.cancel()
            self.LOOP.stop()
            self.LOOP.close()
        except:
            print("MySensors adapter was unable to cleanly close PyMySensors loop. This is not a problem.")


    def remove_thing(self, device_id):
        if self.DEBUG:
            print("-----REMOVING:" + str(device_id))
        
        try:
            ID_to_clear = int(device_id.split('-')[-1])
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
                print("")
                print(">> incoming message > " + str(type_names[message.type]) + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))
        except:
            print("Error while displaying incoming message in console.")
        
        
        
        # When the first message arrives, try to re-create things from persistence, and then ask all nodes to present themselves.
        #try:
        if self.first_request_done == False:
            self.first_request_done = True
            
            try:
                print("self.GATEWAY.metric was set to: " + str(self.GATEWAY.metric))
                self.GATEWAY.metric = self.metric
                print("self.GATEWAY.metric is now set to: " + str(self.GATEWAY.metric))
            except:
                print("Failed to set the PyMySensors object to metric/fahrenheit.")
            try:
                self.try_rerequest() # Asks all nodes to present themselves
            except Exception as ex:
                print("Error while initiating re-request of nodes: " + str(ex))
        #except:
            #print("Error dealing with first incoming message")
        
        
        # Handle the incoming message
        try:
            # If the messages is coming from a device in the MySensors network:
            if message.node_id != 0:
                # first we check if the incoming node_id already has already been presented to the WebThings Gateway.
                try:
                    #print("get_devices = " + str(self.get_devices()))
                    targetDevice = self.get_device("MySensors-" + str(message.node_id)) # targetDevice will be 'None' if it wasn't found.
                    #print("targetDevice = " + str(targetDevice))
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
                                #if self.DEBUG:
                                #self.handle_device_added(device) # This could be removed. Ideally it would only be called after at least one child pas presented itself. On the other hand, it could be useful to show that a device did respond, even if the children couldn't be properly processed.

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
                            print("message.node_id was in self.GATEWAY.sensors")
                            try:
                                if str(self.GATEWAY.sensors[message.node_id].sketch_name) == 'None':
                                    name = 'MySensors-' + str(message.node_id)
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
                                    print("child: " + str(child))
                                    if self.DEBUG:
                                        print("-The PyMySensors node existed, and has child data. Now to present it to the WebThings Gateway. Child = " + str(child))
                                    
                                    if not child.description:
                                        print("-Child had no description")
                                        new_description = 'Property type ' + str(message.sub_type)
                                    else:
                                        new_description = child.description
                                        print("new new description: " + str(new_description))
                                        
                                    if not child.values:
                                        values = {}
                                    else:
                                        values = child.values
                                        print("new new values: " + str(values))
                                        
                                    if not child.type:
                                        print("somehow there was no type data?")
                                        return
                                    
                                    # def add_child(self, new_description, node_id, child_id, main_type, sub_type, values, value):
                                    targetDevice.add_child(new_description, message.node_id, message.child_id, child.type, message.sub_type, values, message.payload)
                                    print("-Finished proces of adding new property on new device. Presenting device to the WebThings Gateway now.")
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



    def scan_usb_ports(self): # Scans for USB serial devices
        initial_serial_devices = set()
        result = {"state":"stable","port_id":[]}
        
        try:    
            ports = prtlst.comports()
            for port in ports:
                if 'USB' in port[1]: #check 'USB' string in device description
                    #if self.DEBUG:
                    #    print("port: " + str(port[0]))
                    #    print("usb device description: " + str(port[1]))
                    if str(port[0]) not in self.initial_serial_devices:
                        self.initial_serial_devices.add(str(port[0]))
                        
        except Exception as e:
            print("Error getting serial ports list: " + str(e))




    def try_rerequest(self):
        # re-request that all nodes present themselves, but only is that thread isn't already running / doesn't already exist.
        try:
            if self.t:
                print("Thread already existed")
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
            try:
                self.t = threading.Thread(target=self.rerequest)
                self.t.daemon = True
                self.t.start()
                if self.DEBUG:
                    print("Re-request thread created")
            except:
                print("Could not create thread")


    def rerequest(self):   
        if self.DEBUG:
            print("Re-requesting presentation of all nodes on the network")
        try:
            self.GATEWAY.send('0;255;3;0;26;0\n') # Ask all nodes within earshot to respond with their node ID's.
                
            # this asks all known devices to re-present themselves. In a future version this request could only be made to nodes where a device property count is lower than expected.
            for index in self.GATEWAY.sensors: #, sensor
                if index != 0:
                    if self.DEBUG:
                        print("<< Requesting presentation from " + str(index))
                    discover_encoded_message = str(index) + ';255;3;0;19;\n'
                    self.GATEWAY.send(discover_encoded_message)
                    #time.sleep(1)
                    sleep(1)
                    
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
        
        # Connection status preference
        try:
            if 'Show connection status' in config:
                print("-Connection status is present in the config data.")
                self.show_connection_status = bool(config['Show connection status'])
                
            if 'Debugging' in config:
                self.DEBUG = config['Debugging']
                print("Debugging enabled")
            else:
                self.DEBUG = False
                
        except:
            print("Error loading part 1 of settings")
            
        
        
        # Metric or Imperial
        try:
            if 'Metric' in config:
                self.metric = bool(config['Metric'])
                if self.metric == False:
                    self.temperature_unit = 'degree fahrenheit'
            else:
                self.metric = True
        except Exception as ex:
            print("Metric/Fahrenheit preference not found." + str(ex))
            
            
        # MQTT username and password
        try:
            if 'MQTT username' in config:
                self.MQTT_username = str(config['MQTT username'])
            else:
                print("No MQTT username set")

            if 'MQTT password' in config:
                self.MQTT_password = str(config['MQTT password'])
            else:
                print("No MQTT password set")
                
        except Exception as ex:
            print("MQTT username and/or password error:" + str(ex))
            
            
        # Now that that we know the desired connection status preference, we quickly recreate all devices.
        try:
            self.recreate_from_persistence()
        except Exception as ex:
            print("Error while recreating after start_persistence: " + str(ex))
            
            
        try:
            if 'Gateway' in config:
                selected_gateway_type = str(config['Gateway'])
                print("-Gateway choice: " + selected_gateway_type)
            else:
                print("Error: no gateway type selected in add-on settings!")
                return
            
            
            if selected_gateway_type == 'USB Serial gateway':
                dev_port = ''
                if 'USB device name' not in config or str(config['USB device name']) == '':
                    if self.DEBUG:
                        print("Port ID was empty, initiating scan of USB serial ports")
                    try:
                        if len(self.initial_serial_devices) == 1:
                            #dev_port = str(self.initial_serial_devices[0])
                            dev_port = next(iter(self.initial_serial_devices))
                            print("Only one serial device found, it's on port " + str(dev_port))
                        elif len(self.initial_serial_devices) > 1:
                            for port_id in self.initial_serial_devices:
                                if self.DEBUG:
                                    print("Scanning port: = " + str(port_id))
                                current_serial_object = serial.Serial(str(port_id), 115200, timeout=1)
                                timeout_counter = 100
                                while( timeout_counter > 0):     # Wait at most 10 seconds for data from the serial port
                                    timeout_counter -= 1
                                    #time.sleep(.1)
                                    sleep(.1)
                                    if int(current_serial_object.inWaiting()) > 0:
                                        timeout_counter = 0
                                    #print(str(timeout_counter))
                                
                                if current_serial_object.inWaiting() > 0:   # If serial data is available, check the first line to see if it is the MySensors gateway device.
                                    ser_bytes = current_serial_object.readline()
                                    decoded_bytes = ser_bytes.decode("utf-8") # Use ASCII decode instead?
                                    if self.DEBUG:
                                        print("Serial data reveived: " + str(decoded_bytes))
                                    if "Gateway startup complete" in decoded_bytes:
                                        print("After a scan the serial gateway device was found on port " + str(port_id))
                                        dev_port = str(port_id)
                                        current_serial_object.close()
                                        break
                                else:
                                    print("The connected serial device did not have any data available. Are you sure it's a MySensors gateway?")
                                current_serial_object.close()
                                
                    except Exception as ex:
                        print("Tried to find serial port, but there was an error: " + str(ex))
                        
                    if dev_port == '':
                        print("Using fallback port /dev/ttyUSB0")
                        dev_port = '/dev/ttyUSB0'
                
                elif str(config['USB device name']) != '':
                    dev_port = str(config['USB device name'])
                    print("USB gateway selected, and custom port id provided: " + str(dev_port))
                    if dev_port not in self.initial_serial_devices:
                        print("Warning, no actual USB device found at specified serial port")
                
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
                print("Bye")
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

class MQTT(object):
    """MQTT client example."""

    # pylint: disable=unused-argument

    def __init__(self, broker, port, keepalive):
        """Setup MQTT client."""
        print("MQTT object init")
        self.topics = {}
        self._mqttc = mqtt.Client()
        self._mqttc.connect(broker, port, keepalive)

    def publish(self, topic, payload, qos, retain):
        """Publish an MQTT message."""
        self._mqttc.publish(topic, payload, qos, retain)

    def subscribe(self, topic, callback, qos):
        """Subscribe to an MQTT topic."""
        print("subscribing to topic " + str(topic))
        if topic in self.topics:
            print("already subscribed")
            return
        
        def _message_callback(mqttc, userdata, msg):
            """Callback added to callback list for received message."""
            #print("calling callback")
            callback(msg.topic, msg.payload.decode('utf-8'), msg.qos)
            
        self._mqttc.subscribe(topic, qos)
        self._mqttc.message_callback_add(topic, _message_callback)
        self.topics[topic] = callback

    def start(self):
        """Run the MQTT client."""
        self._mqttc.loop_start()
        print("Started MQTT client")

    def stop(self):
        """Stop the MQTT client."""
        print('Stop MQTT client')
        self._mqttc.disconnect()
        self._mqttc.loop_stop()


