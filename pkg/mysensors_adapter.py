"""MySensors adapter for Mozilla WebThings Gateway."""

import time
import mysensors.mysensors as mysensors

from gateway_addon import Adapter, Database
from .mysensors_device import MySensorsDevice
from .util import pretty, is_a_number

_TIMEOUT = 3


class MySensorsAdapter(Adapter):
    """Adapter for TP-Link smart home devices."""

    def __init__(self, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
		
        self.GATEWAY = mysensors.SerialGateway('/dev/ttyUSB0', baud=115200, timeout=1.0, reconnect_timeout=10.0, event_callback=self.event, persistence=True, persistence_file='./mysensors.json', protocol_version='2.2')
        time.sleep(10)
        self.GATEWAY.start()
        
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'mysensors-adapter', 'mysensors-adapter', verbose=verbose)

        print("adapter ID = " + self.get_id())

        self.pairing = False
        time.sleep(30)
        self.start_pairing(_TIMEOUT)
        #self.dump()

    
    def event(self, message):
        print()
        print(">>message > id: " + str(message.node_id) + "; child: " + str(message.child_id) + "; subtype: " + str(message.sub_type) + "; payload: " + str(message.payload))
        #print("-message type " + str(message.type))

        
        if message.child_id != 255:
            if message.node_id != 0:
                if is_a_number(message.payload):

                    try:
                        targetNode = self.get_device(str(message.node_id))
                        #print("self.get_device(str(message.node_id) gave: " + str(targetNode)) # check if this is 'None' or something useable.
                        
                        if str(targetNode) != 'None':
                            #print("targetNode = " + str(targetNode))
                            try:
                                if is_a_number(message.payload):
                                    
                                    #alreadyAttachedProperties = targetNode.get_property_descriptions()
                                    #print("alreadyAttachedProperties = " + str(alreadyAttachedProperties))
                                    
                                    targetPropertyID = str(message.child_id) + "-" + str(message.sub_type) # e.g. 5-2
                                    targetProperty = targetNode.find_property(targetPropertyID)
                                    #print("targetProperty = " + str(targetProperty))
                                    
                                    targetNode.set_property(str(message.child_id),float(message.payload))
                                    targetNode.notify_property_changed(targetProperty)
                                    print("-adapter updated property")

                            except Exception as ex:
                                print("Couldn't update existing property (does it exist?): " + ex)
                        else:
                            #print("Device doesn't exist (yet)")
                            pass
                            
                    except Exception as ex:
                        print("target device does not exist (yet)")
                        print(ex)
            
        #try:
        #    pretty(self.devices)
        #    existingDevices = self.get_devices()
        #    print("existingDevices = " + str(existingDevices))
        #except Exception as ex:
        #    print("devices list does not exist (yet)?")
        #    print(ex)
        
        
    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.

        timeout -- Timeout in seconds at which to quit pairing
        """
        print()
        print("PAIRING INITIATED")
        if self.pairing:
            print("-already pairing")
            return

        self.pairing = True
        
        for nodeIndex in self.GATEWAY.sensors:
            if self.GATEWAY.sensors[nodeIndex].sensor_id != 0: # the gateway has index 0. It should probably not be added as a device. TODO: this could be an option.
                try:
                    print("-node index = " + str(nodeIndex))
                    self._add_device(self.GATEWAY.sensors[nodeIndex])
                    
                    print("-Adding process complete")
                except Exception as ex:
                    print("-failed to add new device:" + str(ex))
                    
            if not self.pairing:
                break
                
        self.pairing = False

    def _add_device(self, node):
        """
        Add the given device, if necessary.

        dev -- the device object from pyMySensors
        """

        if str(node.sensor_id) not in self.devices:
            print("+ADDING DEVICE: " + str(node.sketch_name))
            device = MySensorsDevice(self, node.sensor_id, node)
            print("almost")
            self.handle_device_added(device)
            return
        else:
            print("-device already added")

    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
