"""MySensors adapter for Mozilla WebThings Gateway."""

import mysensors.mysensors as mysensors

from gateway_addon import Property
from .util import pretty, is_a_number, get_int_or_float

class MySensorsProperty(Property):
    """MySensors property type."""

    def __init__(self, device, name, description, values, value, node_id, child_id, main_type, subchild_id): # subchild_id is V_TYPE
        """
        Initialize the object.

        device -- the Device this property belongs to
        name -- name of the property
        description -- description of the property, as a dictionary
        value -- current value of this property
        """
        #print()
        
        #print("-device " + str(device))
        #print("-name: " + str(name))
        #print("-description: " + str(description))
        #print("-value: " + str(value))
        try:
            if device.adapter.DEBUG:
                print("Property: initialising")
            Property.__init__(self, device, name, description)
            self.set_cached_value(value)

            #self.device = device
            self.node_id = node_id # These three are used in the set_value function to send a message back to the proper node in the MySensors network.
            self.child_id = child_id
            self.main_type = main_type
            self.subchild_id = subchild_id

            self.device = device
            self.name = name
            self.title = name
            self.description = description
            self.values = values
            self.value = value

            #self.set_cached_value(value)
            #self.value = value #hmm, test
            #self.device = device
            if device.adapter.DEBUG:
                print("property value = " + str(self.value))
            #print("self.device inside property = " + str(self.device))
            #self.device.notify_property_changed(self)
            #print("property init done")
            
        except Exception as ex:
            print("inside adding property error: " + str(ex))


    def set_value(self, value):
        """
        Set the current value of the property.

        value -- the value to set
        """
        
        #if device.adapter.DEBUG:
        if self.device.adapter.DEBUG:
            print("<< Sending update to MySensors network")
        #print("->name " + str(self.name))
        #print("->devi " + str(self.device))
        #print("->node_id " + str(self.node_id))
        #print("->child_id " + str(self.child_id))
        #print("->subchild " + str(self.subchild_id))
        

        try:
            if self.device.adapter.DEBUG:
                print("<< User initiated message to MySensors network: " + str(value))
            # To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
            intNodeID = int(float(self.node_id))
            intChildID = int(float(self.child_id))
            intSubchildID = int(float(self.subchild_id))

            if is_a_number(value):
                #print("-will be sent as int or float")
                new_value = get_int_or_float(value)
                #new_value = float( int( new_value * 100) / 100)
                if self.device.adapter.DEBUG:
                    print("tamed float = " + str(new_value))
                
                #if new_value == 0:
                #    new_value = False
                #if new_value == 1:
                #    new_value = True                
                
            else:
                if self.device.adapter.DEBUG:
                    print("-will be sent as string")
                new_value = str(value)
            
            try:
                #print("-target values inside PyMySensors A: " + str(self.device.adapter.GATEWAY.sensors[self.node_id].children[self.child_id].values))

                #print("-target values inside PyMySensors B: " + str(self.device.adapter.GATEWAY.sensors[intNodeID].children[intChildID].values))
                self.device.adapter.GATEWAY.set_child_value(intNodeID, intChildID, intSubchildID, new_value) # here we send the data to the MySensors network.
                #print("-updated values inside PyMySensors: " + str(self.device.adapter.GATEWAY.sensors[intNodeID].children[intChildID].values))
            except Exception as ex:
                print("set value inside PyMySensors object failed. Error: " + str(ex))

        except Exception as ex:
            print("set_value inside property object failed. Error: " + str(ex))


    # I'm not sure that this function is ever used..
    def update(self, value): 
        """
        Update the current value, if necessary.

        value -- the value to update
        """
        
        if self.device.adapter.DEBUG:
            print("property -> update")
        
        try:
            
            # Heater/Thermostat modifications
            if self.main_type == 14 and self.subchild_id == 16: # S_HEATER and V_TRIPPED
                if value == 0:
                    value = "off"
                else:
                    value = "heating"
            
            # Support for the new Lock capability turned out to be a bit too complex.
            #if self.main_type == 19 and self.subchild_id == 36: # S_LOCK and V_LOCK_STATUS
            #    if value == 1:
            #        value = "locked"
            #    else:
            #        value = "unlocked"
        
        except:
            print("error translating value from boolean to thermostat string")
        
        
        if value != self.value:
            self.set_cached_value(value)
            self.device.notify_property_changed(self)
