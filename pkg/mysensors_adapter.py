"""MySensors adapter for Mozilla WebThings Gateway."""

import os
from os import path
import sys

sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

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
                self.old_persistence_file_path = os.path.join(
                    path,
                    'mysensors-adapter-persistence.json'
                )
        self.addon_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', 'mysensors-adapter')
        self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', 'mysensors-adapter','mysensors-adapter-persistence.json')
        
        # Persistence files should move to a new location.
        try:
            if os.path.isfile(self.old_persistence_file_path) and ( not os.path.isfile(self.persistence_file_path)):
                os.system('cp ' + self.old_persistence_file_path + ' ' + self.persistence_file_path)
        except:
            print("Error copying old persistence file to new location")
        
        self.metric = True
        self.temperature_unit = 'degree celsius'
        self.DEBUG = True
        self.show_connection_status = True
        self.first_request_done = False
        self.initial_serial_devices = set()
        self.optimize = True
        self.running = True
        
        self.separation_s = [3,4] # S types to separate V types on. S_binary and S_dimmer
        self.separation_v = [2,3] # V types to seperate if on the above S-type. V_status and V_percentage
        
        self.MQTT_username = ""
        self.MQTT_password = ""
        self.MQTT_out_prefix = "mygateway1-out"
        self.MQTT_in_prefix = "mygateway1-in"
        
        self.things_list = []
        
        self.timeout_seconds = 0 # the default is a day
        self.last_seen_timestamps = {}
        self.previous_heartbeats = {}
        
        try:
            print("Making initial scan of USB ports")
            self.scan_usb_ports()
        except:
            print("Error during initial scan of usb ports")
            
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config (and initialising PyMySensors library?): " + str(ex))



    def clock(self):
        """ Runs every minute and updates which devices are still connected """
        if self.DEBUG:
            print("clock thread init")
        while self.running:

            try:
                if self.DEBUG:
                    print("CLOCK TICK")
                current_time = int(time.time())
                for nodeIndex in self.last_seen_timestamps:
                    if self.DEBUG:
                        print("- nodeIndexin last_seen_timestamps: " + str(nodeIndex))
                    
                    pymy_heartbeat = 0
                    if nodeIndex in self.GATEWAY.sensors:
                        if self.DEBUG:
                            print("nodeIndex was in self.GATEWAY.sensors")
                        try:
                            # Some devices don't regularly send data, such as the smart lock, but they do send a 'heartbeat' signal to let us know they are still up and running.
                            # Here we check if the heartbeat counter has changed since the previous clock tick. If it has, it gets a fresh timestamp.
                            if int(self.GATEWAY.sensors[nodeIndex].heartbeat) != int(self.previous_heartbeats[nodeIndex]):
                                self.previous_heartbeats[nodeIndex] = int(self.GATEWAY.sensors[nodeIndex].heartbeat)
                                self.last_seen_timestamps[nodeIndex] = int(time.time())
                                if self.DEBUG:
                                    print("updated timeout timestamp using heartbeat data")
                        except Exception as ex:
                            print("Error trying to get heartbeat for timeout: " + str(ex))
                    
                    # Has the devices recently given some sign that it's alive? If not, set it to disconnected.
                    # This is only done for devices that have recently crossed the timeout threshold.
                    # A small window in which we tell the Gateway to set it to disconnected. This we we don't update the gateway's connection status too often.
                    if int(self.last_seen_timestamps[nodeIndex]) < current_time - self.timeout_seconds and int(self.last_seen_timestamps[nodeIndex]) > ((current_time - self.timeout_seconds) - 120): 
                        # This device hasn't been seen in a while.
                        if self.DEBUG:
                            print(str(nodeIndex) + " hasn't been seen in a while")
                        try:
                            targetDevice = self.get_device("MySensors-" + str(nodeIndex))
                            if str(targetDevice) != 'None':
                                targetDevice.connected_notify(False)
                                if self.DEBUG:
                                    print("-Setting device status to not connected.")
                            else:
                                print("Strange, couldn't actually find the device to set it to disconnected")
                        except:
                                print("-Error updating state to disconnected")
                    else:
                        if self.DEBUG:
                            print(str(nodeIndex) + " has been spotted recently enough")
            except Exception as ex:
                print("Clock error: " + str(ex))

            time.sleep(60)
        





    def recreate_from_persistence(self):
        if self.DEBUG:
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
                    
                    # Add device to list of timestamps
                    if self.timeout_seconds != 0:
                        try:
                            self.last_seen_timestamps.update( {int(nodeIndex):0} ) # They all start out with a time of 0, pretending they were last spotted in 1970.
                            self.previous_heartbeats.update( {int(nodeIndex):0} )
                        except:
                            print("Couldn't add device to timestamp list")
                    
                    # Recreate
                    try:
                        if str(node['sketch_name']) == 'None':
                            name = 'MySensors-{}'.format(nodeIndex)
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
                            if self.timeout_seconds != 0:
                                if self.adapter.DEBUG:
                                    print("Showing device as disconnected. It will be set to 'connected' as soon as it actually makes a connection.")
                                # Create a handle to the new device, and use its notify function.
                                targetDevice = self.get_device("MySensors-" + str(nodeIndex))
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
            
        if self.DEBUG:
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
                    self.GATEWAY = mysensors.AsyncMQTTGateway(self.MQTTC.publish, self.MQTTC.subscribe, in_prefix=self.MQTT_in_prefix,
                        out_prefix=self.MQTT_out_prefix, retain=True, event_callback=self.mysensors_message,
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
            self.running = False
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
            obj = self.get_device(device_id)        
            self.handle_device_removed(obj)                     # Remove from device dictionary
            print("Removed device")
        except:
            print("Could not remove things from devices")
            
        try:
            if device_id.count('-') == 1:
                ID_to_clear = int(device_id.split('-')[-1])
                del self.GATEWAY.sensors[ID_to_clear]           # Remove from PyMysensors persistence
                print("Removed device from persistence too")
        except:
            print("REMOVING MYSENSORS THING FAILED") 


    def mysensors_message(self, message):
        # Show some human readable details about the incoming message
        extraDevice = None # Holds a copy of a property, used for optimization with voice interfaces.
        extraProperty = None
        
        try:
            if self.DEBUG:
                print("")
                #print(str(vars(message)))
            
            type_names = ['presentation','set','request','internal','stream']
            if self.DEBUG:
                print(">> incoming message > " + str(type_names[message.type]) + " > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))
        except Exception as ex:
            print("Error while displaying incoming message in console: " + str(ex))
        
        
        
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
                
                # Add a last-seen timestamp (if the feature is enabled)
                if self.timeout_seconds != 0:
                    try:
                        if self.DEBUG:
                            print(str(message.node_id) + " gets timestamp " + str(int(time.time())))
                        self.last_seen_timestamps.update( { message.node_id: int(time.time()) } )
                    except Exception as ex:
                        print("error updating timestamp dictionary: " + str(ex))
                
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
                    if targetDevice == None:
                        if message.sub_type == 11: # holds the sketch name, which will be the name of the new device
                            if self.DEBUG:
                                print("-Internally presented device did not exist in the gateway yet. Adding now.")
                            try:
                                device = MySensorsDevice(self, message.node_id, str(message.payload))
                            except Exception as ex:
                                print("-Failed to add new device from internal presentation: " + str(ex))
                    else:
                        if targetDevice.connected == False:
                            targetDevice.connected = True
                            targetDevice.connected_notify(True)


                #SET
                # The message is a 'set' message. This should update a property value or, if the property doesn't exist yet, create it.
                elif message.type == 1:
                    #print("SET")
                    
                    # Get the value from the message
                    new_value = None
                    try:
                        if is_a_number(message.payload):
                            new_value = get_int_or_float(message.payload)
                        else:
                            new_value = str(message.payload)
                    except Exception as ex:
                        print("could not interpret payload: " + str(ex))
                        return
                    #print("New update value:" + str(new_value))

                    # If there is a 'set' message but the device for this node somehow doesn't exist yet, then we should quickly create it.
                    if targetDevice == None:
                        if self.DEBUG:
                            print("Incoming 'set' message, but device doesn't exist (yet). If possible, will try to quickly create the device using persistence data.") # Perhaps the persistence data can help. Not sure if this situtation is even possible now that persistence is always used.
                        if message.node_id in self.GATEWAY.sensors:
                            print("message.node_id was in self.GATEWAY.sensors")
                            try:
                                # Generate human readable name for the thing
                                if str(self.GATEWAY.sensors[message.node_id].sketch_name) == 'None':
                                    name = 'MySensors-' + str(message.node_id)
                                    if self.DEBUG:
                                        print("-Node was in persistence, but no sketch name found. Generated a generic name.")
                                else:
                                    name = str(self.GATEWAY.sensors[message.node_id].sketch_name)
                                print("-Name for the new device is: " + name)
                                
                                # Add the node to the devices list
                                device = MySensorsDevice(self, message.node_id, name)
                                self.handle_device_added(device)
                                
                                # Now try to get that device handle again.
                                try:
                                    targetDevice = self.get_device("MySensors-" + str(message.node_id)) # targetDevice will be 'None' if it wasn't found.
                                except Exception as ex:
                                    print("Error while checking if node exists as device AGAIN: " + str(ex))
                        
                            except Exception as ex:
                                print("-Failed to add new device: " + str(ex))
                        else:
                            print("Node ID not found in persistence file, so cannot re-create device. Please restart the node.")
                            
                        
                    # Here we can be sure that the target thing exists (thanks to the check above)
                    if targetDevice != None:
                        #print("targetDevice = " + str(targetDevice))
                        if targetDevice.connected == False:
                            targetDevice.connected = True
                            targetDevice.connected_notify(True)
                        
                        if message.sub_type != 43: # avoid creating a property for V_UNIT_PREFIX
                            
                            
                            targetPropertyID = str(message.node_id) + "-" + str(message.child_id) + "-" + str(message.sub_type) # e.g. 2-5-36
                            try:
                                targetProperty = targetDevice.find_property(targetPropertyID)
                            except Exception as ex:
                                print("Error getting target property: " + str(ex))
                                
                            # The property does not exist yet:
                            if targetProperty == None: 
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
                            if targetProperty != None:
                                targetProperty.update(new_value)
                
                # Try to also update the extra device/property, if it exists.
                if self.optimize:
                    try:
                        extraDevice = self.get_device("MySensors-" + str(message.node_id) + "-" + str(message.child_id))
                        if extraDevice != None:
                            extraProperty = extraDevice.find_property(targetPropertyID)
                            extraProperty.update(new_value)
                            if self.DEBUG:
                                print("Optimization: updated extra thing: MySensors-" + str(message.node_id) + "-" + str(message.child_id))
                    except Exception as ex:
                        print("Error while updating extra device")            


                


        except Exception as ex:
            print("-Failed to handle message:" + str(ex))



    def scan_usb_ports(self): # Scans for USB serial devices
        if self.DEBUG:
            print("Scanning USB serial devices")
        initial_serial_devices = set()
        result = {"state":"stable","port_id":[]}
        
        try:    
            ports = prtlst.comports()
            for port in ports:
                if self.DEBUG:
                    print("possible port: " + str(port))
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
                if self.DEBUG:
                    print("Thread already existed")
                if not self.t.is_alive():
                    # Restarting request for presentation of nodes
                    self.t = threading.Thread(target=self.rerequest)
                    self.t.daemon = True
                    self.t.start()
                    if self.DEBUG:
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
        
        
        
        # Debug
        try:
            if 'Debugging' in config:
                self.DEBUG = bool(config['Debugging'])
                if self.DEBUG:
                    print("Debugging is set to: " + str(self.DEBUG))
            else:
                self.DEBUG = False
                
        except:
            print("Error loading debugging preference")
            
            
        
        # Timeout period
        try:
            if 'Timeout period' in config:
                if self.DEBUG:
                    print("-Timeout period preference is present in the config data.")
                self.timeout_seconds = int(config['Timeout period']) * 60
                if self.timeout_seconds != 0:
                    if self.DEBUG:
                        print("Starting the internal clock")
                    try:
                        t = threading.Thread(target=self.clock)
                        t.daemon = True
                        t.start()
                    except:
                        print("Error starting the clock thread")
                else:
                    print("-Timeout period was set to 0, so will not check for timeouts.")    
                
            else:
                print("Timeout period was not in config")
        except Exception as ex:
            print("Timeout period preference error:" + str(ex))
            
        
        
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
            
            
        # MQTT prefixes
        try:
            if 'MQTT in prefix' in config:
                self.MQTT_in_prefix = str(config['MQTT in prefix'])
            else:
                print("No MQTT in prefix set")

            if 'MQTT out prefix' in config:
                self.MQTT_out_prefix = str(config['MQTT out prefix'])
            else:
                print("No MQTT out prefix set")
                
        except Exception as ex:
            print("MQTT username and/or password error:" + str(ex))
            
            
            
        # Now that that we know the desired connection status preference, we quickly recreate all devices.
        try:
            self.recreate_from_persistence()
        except Exception as ex:
            print("Error while recreating after start_persistence: " + str(ex))

        try:
            self.send_in_the_clones()
        except Exception as ex:
            print("Error while optimizing: " + str(ex))

            
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
                                        print("Serial data received: " + str(decoded_bytes))
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
                
        try:
            self.send_in_the_clones()
        except Exception as ex:
            print("Error while optimizing: " + str(ex))  
            
        return



    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
        
        """
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
        """

    def send_in_the_clones(self):
        # Generate additional buttons if so desired.
        if self.optimize:
            if self.DEBUG:
                print("")
                print("Creating extra clones of properties from devices with a lot of toggles.")
            # Check if the device already has an 'OnOff property in devices
            
            new_devices_to_add = []
            properties_to_remove_OnOff_from = []
            try:
                for device_name in self.get_devices():
                    if self.DEBUG:
                        print("__device_name = " + str(device_name))
                    #onOff_count = 0
                    
                    try:
                        targetDevice = self.get_device(device_name)
                        #print("targetDevice = " + str(targetDevice))
                        for device_property in targetDevice.get_property_descriptions():

                            property_object = targetDevice.find_property(device_property)
                            #print("property object: " + str(vars(property_object)))

                            try:
                                #print("property_object.description[@type] = " + str(property_object.description['@type']))
                                
                                if int(property_object.child_id) > 100:
                                    
                                #if property_object.description['@type'] == "OnOffProperty":
                                #    onOff_count += 1
                            #except:
                                #print("no @type set")
                            #    pass
                            
                        #print("onOff_count = " + str(onOff_count))
                        
                    #except Exception as ex:
                    #    print("Error scanning for optimizable devices: " + str(ex))
                    
                    
                    #if onOff_count > 1:
                    #    onOff_count = 0
                    #    for device_property in targetDevice.get_property_descriptions():
                    #        property_object = targetDevice.find_property(device_property)
                    #        try:
                                #if property_object.description['@type'] == "OnOffProperty":
                                #    onOff_count += 1
                                #    
                                #    if onOff_count > 1:
                                        # Set the @type of the original device to None? That solves a lot of issues: it won't be copied again, and it makes the original device more predictable.. in a way. Only one toggle will be the main one.
                                #        properties_to_remove_OnOff_from.append(property_object)
                                        
                                    # Generate a predictable name
                                    extra_name = str(property_object.node_id) + "-" + str(property_object.child_id)
                                    #print(" extra_name = " + str(extra_name))
                                    property_label = str(property_object.description['label'])
                                    
                                    #try:
                                    #    property_label = str(targetDevice.title) + " - " + property_label
                                    #except:
                                    #    print("upgrade to at least version 0.9 of the WebThings Gateway")
                                        
                                    print("extra property title = " + str(property_label))
                                    # Check if the extra thing hasn't already been created
                                                                    # Add the node to the devices list
                                    device = MySensorsDevice(self, extra_name, property_label)
                                    try:
                                        #print("))get ID " + str(device.get_id()))
                                        #add_child(self, new_description, node_id, child_id, main_type, sub_type, values, value):
                                        device.add_child(property_label,property_object.node_id,property_object.child_id,property_object.main_type, property_object.subchild_id, property_object.values, property_object.value)
                                        new_devices_to_add.append(device)
                                        #print("CHILD ADDED!")
                                    except Exception as ex:
                                        print("Could not add child to thing clone: " + str(ex))

                                    # Now try to get that device handle again.
                                    #try:
                                    #    targetDevice = self.get_device("MySensors_" + str(property_object.child_id)) # targetDevice will be 'None' if it wasn't found.
                                    #except Exception as ex:
                                    #    print("Error while checking if node exists as device AGAIN: " + str(ex))

                            except Exception as ex:
                                print("Error cloning: " + str(ex))
                    except Exception as ex:
                        print("Error getting target device while cloning: " + str(ex))
                    
                    
            except Exception as ex:
                print("Error creating extra buttons: " + str(ex))
            
            try:
                for new_device in new_devices_to_add:
                    self.handle_device_added(new_device)
                    if self.DEBUG:
                        print("Added clone: " + str(new_device.title))
            except:
                print("could not add the clones to the internal devices list")
                
            try:
                for donor_property in properties_to_remove_OnOff_from:
                    #print("")
                    #print(str(vars(donor_property)))
                    donor_property.description['@type'] = None # Will this already do that?
                    if self.DEBUG:
                        print("Removed capability from " + str(donor_property.title))
                    
            except:
                print("Could not remove OnOff property from the clone's donor property")















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


