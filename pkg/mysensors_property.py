"""MySensors adapter for Mozilla WebThings Gateway."""

import mysensors.mysensors as mysensors

from gateway_addon import Property
from .util import pretty, is_a_number, get_int_or_float

class MySensorsProperty(Property):
    """MySensors property type."""

    def __init__(self, device, name, description, value, node_id, child_id, subchild_id):
        """
        Initialize the object.

        device -- the Device this property belongs to
        name -- name of the property
        description -- description of the property, as a dictionary
        value -- current value of this property
        """
        print()
        print("initialising property")
        #print("-device " + str(device))
        #print("-name: " + str(name))
        #print("-description: " + str(description))
        #print("-value: " + str(value))
        try:
            Property.__init__(self, device, name, description)
            self.set_cached_value(value)

            #self.device = device
            self.node_id = node_id # These three are used in the set_value function to send a message back to the proper node in the MySensors network.
            self.child_id = child_id
            self.subchild_id = subchild_id

            #self.device = device
            #self.name = name
            #self.description = description
            #self.value = value

            #self.set_cached_value(value)
            #self.value = value #hmm, test
            #self.device = device
            #print("property value = " + str(self.value))
            #print("self.device inside property = " + str(self.device))
            self.device.notify_property_changed(self)
            print("property init done")
            
        except Exception as ex:
            print("inside adding property error: " + str(ex))


    def set_value(self, value):
        """
        Set the current value of the property.

        value -- the value to set
        """
        
        #print("property -> set_value")
        #print("->name " + str(self.name))
        #print("->devi " + str(self.device))
        #print("->node_id " + str(self.node_id))
        #print("->child_id " + str(self.child_id))
        #print("->subchild " + str(self.subchild_id))
        

        try:
            print("<< MESSAGE FROM WEBTHINGS GATEWAY TO MYSENSORS NETWORK: " + str(value))
            # To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
            intNodeID = int(float(self.node_id))
            intChildID = int(float(self.child_id))
            intSubchildID = int(float(self.subchild_id))

            if is_a_number(value):
                new_value = get_int_or_float(value)
            else:
                new_value = str(value)
            
            try:
                #print("-target values inside PyMySensors A: " + str(self.device.adapter.GATEWAY.sensors[self.node_id].children[self.child_id].values))

                #print("-target values inside PyMySensors B: " + str(self.device.adapter.GATEWAY.sensors[intNodeID].children[intChildID].values))
                self.device.adapter.GATEWAY.set_child_value(intNodeID, intChildID, intSubchildID, new_value) # here we send the data to the MySensors network.
                #print("-updated values inside PyMySensors: " + str(self.device.adapter.GATEWAY.sensors[intNodeID].children[intChildID].values))
            except Exception as ex:
                print("send value inside property object failed. Error: " + str(ex))

        except Exception as ex:
            print("set_value inside property object failed. Error: " + str(ex))


    # I'm not sure that this function is ever used..
    def update(self, value): 
        """
        Update the current value, if necessary.

        value -- the value to update
        """
        
        print("property -> update")
        
        if value != self.value:
            self.set_cached_value(value)
            self.device.notify_property_changed(self)
