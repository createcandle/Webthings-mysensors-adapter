"""MySensors adapter for Mozilla WebThings Gateway."""


import threading
import time
import mysensors.mysensors as mysensors

from gateway_addon import Device
from .mysensors_property import MySensorsProperty
from .util import pretty, is_a_number, get_int_or_float



class MySensorsDevice(Device):
    """MySensors device type."""

    def __init__(self, adapter, _id, sketch_name):
        """
        Initialize the object.

        adapter -- the Adapter managing this device
        _id -- ID of this device
        sketch_name -- The MySensors node name
        index -- index inside parent device
        """
        
        #self._id = "MySensors_" + str(_id)
        self._id = 'MySensors-{}'.format(_id)
        
        #print("Device init: " + str(node.sketch_name))
        Device.__init__(self, adapter, _id)
        
        self.adapter = adapter
        self.id = "MySensors_" + str(_id)
        #self._id = str(_id)
        self.name = sketch_name
        self.description = sketch_name
        self._type = [] # TODO: isn't this deprecated?
        self.properties = {}
        #print("device self.properties at init: " + str(self.properties))
        self.connected = False # Will be set to true once we receive an actual message from the node. # TODO: is this still used?



    def add_child(self, new_description, node_id, child_id, main_type, sub_type, values, value):
        #print()
        print("+ DEVICE.ADD_CHILD with child_id: " + str(child_id))
        


        # PREFIX
        # First, let's see if there's a prefix. If there is, we should scrape it from the child's value object
        prefix = '' # prefix starts as an empty string.
        try:
            
            #if not child.description:
            #    print("-Child had no description")
            #    new_description = 'Property type ' + str(sub_type)
            #else:
            #    new_description = child.description

            decription_addendum = '' # If a child has multiple values (yes this is possible..) we should give them all a different name.
            value_counter = 0
            for childSubType in values: # The values dictionary can contain multiple items. We loop over each one.
                if childSubType == 43: # If this is a prefix, then don't turn it into a property.
                    print("-Found a prefix")
                    prefix = str(values[childSubType])
                else:
                    value_counter += 1
                    if childSubType == sub_type and value_counter > 1:
                        if self.adapter.DEBUG:
                            print("-Found multiple properties with potentially the potential same name")
                        decription_addendum = ' ' + str(value_counter)
                        
            new_description = new_description + decription_addendum # this adds a number at the end of the property if there would be more than one with the same name.
            #print("new_description = " + str(new_description))
        except:
            print("Weird: error while looking for a prefix")


        try:
            new_node_id = str(node_id) #str(message.node_id)
            new_child_id = str(child_id) #str(message.child_id)
            #new_sub_type = str(message.sub_type)
            #new_type = type
            new_main_type = int(main_type)
            new_sub_type = int(sub_type)
            #new_value = str(value)
            # 
            
            if is_a_number(value):
                new_value = get_int_or_float(value)
            else:
                new_value = str(value)

            targetPropertyID = str(new_node_id) + "-" + str(new_child_id) + "-" + str(new_sub_type) # e.g. 2-5-36
            
            if self.adapter.DEBUG:
                # required: new_value, new_node_id, new_child_id, new_sub_type
                print("new_description = " + str(new_description))
                print("node_id = " + str(new_node_id))
                print("child_id = " + str(new_child_id))
                print("new_main_type: " + str(new_main_type))
                print("sub_type = " + str(new_sub_type))
                print("value = " + str(new_value))
                
                print("targetPropertyID = " + str(targetPropertyID))
            

            if targetPropertyID in self.properties:
                print("Device; ERROR - property already exists?")
                return


        except Exception as ex:
            print("Error during preparation to add new property: " + str(ex))


        try:
            if new_main_type == 0:                         # Door
                if new_sub_type == 16: # V_TRIPPED
                    self._type.append('DoorSensor')           
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OpenProperty',
                            'label': new_description,
                            'type': 'boolean',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

                if new_sub_type == 15: # V_ARMED
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 1:                       # Motion
                if new_sub_type == 16: # V_TRIPPED
                    self._type.append('MotionSensor')   
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'MotionProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 15: # V_ARMED
                    self._type.append('OnOffSwitch')                       
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 2:                       # Smoke
                if new_sub_type == 16: # V_TRIPPED
                    self._type.append('Alarm')           
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'AlarmProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 15: # V_ARMED
                    #self._type.append('OnOffSwitch')                       
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 3:                       # Binary
                if new_sub_type == 2: # V_STATUS
                    self._type.append('OnOffSwitch')           
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 17: # V_WATT (power meter)
                    #if 'OnOffSwitch' in self._type:
                    #    self._type.remove('OnOffSwitch')
                    self._type.append('EnergyMonitor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'InstantaneousPowerProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'watt',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 4:                       # Dimmer
                if new_sub_type == 2: # V_STATUS
                    #self._type.append('Light')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 3: # V_PERCENTAGE
                    #self._type.append('Light')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'BrightnessProperty',
                            'label': new_description,
                            'minimum': 0,
                            'maximum': 100,
                            'step': 1,
                            'type': 'integer',
                            'unit': 'percent',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 17: # V_WATT
                    #self._type.append('EnergyMonitor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'InstantaneousPowerProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'watt',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 5:                       # Window covers (percentage)
                if new_sub_type == 3: # V_PERCENTAGE
                    self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LevelProperty',
                            'label': new_description,
                            'minimum': 0,
                            'maximum': 100,
                            'step': 1,
                            'type': 'integer',
                            'unit': 'percent',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 30: # V_DOWN
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 29 or new_sub_type == 31: # V_UP and V_STOP
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)



            elif new_main_type == 6:                       # Temperature
                if new_sub_type == 0: # V_TEMP
                    self._type.append('TemperatureSensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'TemperatureProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'degree celsius', # optional for the future:   unit: units === 'imperial' ? 'degree fahrenheit' : 'degree celsius',
                            'readOnly': True,
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 7:                       # Humidity
                if new_sub_type == 1: # V_HUM
                    self._type.append('MultiLevelSensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LevelProperty',
                            'label': new_description,
                            'minimum': 0,
                            'maximum': 100,
                            'type': 'number',
                            'unit': 'percent',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 8:                       # Barometer
                if new_sub_type == 4: # V_PRESSURE (atmospheric pressure)
                    self._type.append('MultiLevelSensor')                
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LevelProperty',
                            'label': new_description,
                            'minimum': 900,
                            'maximum': 1100,
                            'type': 'number',
                            'unit': 'hPa',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 5: # V_FORECAST (weather prediction)
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 9:                       # Wind
                if new_sub_type == 8 or new_sub_type == 9: # V_WIND and V_GUST     
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 10: # V_DIRECTION (of wind)
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

                    
            elif new_main_type == 10:                      # Rain
                if new_sub_type == 6: # V_RAIN
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 7: # V_RAINRATE
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 11:                      # UV level
                if new_sub_type == 11: # V_UV
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

                    
            elif new_main_type == 12:                      # Weight
                if new_sub_type == 12: # V_WEIGHT
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

            elif new_main_type == 13:                      # Power measuring device, like power meters
                if new_sub_type == 17: # V_WATT
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'InstantaneousPowerProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'watt',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)



            elif new_main_type == 14:                      # Heater
                if new_sub_type == 0: # V_TEMP
                    self._type.append('TemperatureSensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'TemperatureProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'degree celsius',
                            'readOnly': True,
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 45: # V_HVAC_SETPOINT_HEAT
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            'minimum':0,
                            'maximum':150,
                            'type': 'number',
                            'unit': 'degree celsius',
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 21: # V_HVAC_FLOW_STATE
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            #'title': 'Mode',
                            'type': 'string',
                            'enum': [
                                'Off',
                                'HeatOn',
                                'CoolOn',
                                'AutoChangeOver'
                              ]
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 2: #V_status
                    #self._type.append('BinarySensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'BooleanProperty',
                            'label': new_description,
                            'type': 'boolean',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                    
                # This is out of spec for MySensors:
                if new_sub_type == 16: #V_TRIPPED
                    #self._type.append('BinarySensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'BooleanProperty',
                            'label': new_description,
                            'type': 'boolean',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                    

            elif new_main_type == 15:                      # Distance
                if new_sub_type == 13: #V_DISTANCE
                    #self._type.append('MultiLevelSensor')
                    if prefix != '':
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'unit': prefix,
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)
                    else:
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 16:                      # Light level
                if new_sub_type == 23: #V_LIGHT_LEVEL
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'minimum': 0,
                            'maximum': 100,
                            'step': 1,
                            'type': 'integer',
                            'unit': 'percent',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 37: #V_LEVEL
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'unit': 'Lux',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 17:                      # Arduino node. This should not be turned into a property.
                pass #          

            elif new_main_type == 18:                      # Arduino repeater. This should not be turned into a property.
                pass

            elif new_main_type == 19:                      # Lock                        
                if new_sub_type == 36: # V_LOCK_STATUS
                    self._type.append('OnOffSwitch')                    
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 20:                      # Ir sender/receiver device
                pass       


            elif new_main_type == 21:                      # Water flow
                if new_sub_type == 37: # V_LEVEL
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 22:                      # Air quality
                if new_sub_type == 37: # V_LEVEL
                    if prefix != '':
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'unit': prefix,
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)
                    else:
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 23:                      # CUSTOM
                if new_sub_type == 48: # V_CUSTOM
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 24:                      # S_DUST
                if new_sub_type == 37: # V_LEVEL
                    if prefix != '':
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'unit': prefix,
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)
                    else:
                        self.properties[targetPropertyID] = MySensorsProperty(
                            self,
                            targetPropertyID,
                            {
                                'label': new_description,
                                'type': 'number',
                                'readOnly': True,
                            },
                            new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 25:                      # Scene controller
                if new_sub_type == 19 or new_sub_type == 20: # V_SCENE_ON and V_SCENE_OFF
                    self._type.append('PushButton')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'PushedProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 26 or new_main_type == 27:                      # RGB light or RGB light with separate white level
                #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
                #pass #todo
                if new_sub_type == 2: # V_STATUS
                    self._type.append('Light')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 3: # V_PERCENTAGE
                    #self._type.append('Light')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'BrightnessProperty',
                            'label': new_description,
                            'minimum': 0,
                            'maximum': 100,
                            'step': 1,
                            'type': 'integer',
                            'unit': 'percent',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

            #elif new_main_type == 27:                      # RGB light with separate white level
            #    #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
            #    pass #todo


            elif new_main_type == 28:                      # Color sensor
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        'label': new_description,
                        'type': 'string',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 29:                      # Thermostat / HVAC
                if new_sub_type == 21: # V_HVAC_FLOW_STATE
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            #'title': 'Mode',
                            'type': 'string',
                            'enum': [
                                'Off',
                                'HeatOn',
                                'CoolOn',
                                'AutoChangeOver'
                              ]
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 47: # V_HVAC_FLOW_MODE
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            #'title': 'Mode',
                            'type': 'string',
                            'enum': [
                                'Auto',
                                'ContinuousOn',
                                'PeriodicOn'
                              ]
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 47: # V_HVAC_SPEED
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            #'title': 'Mode',
                            'type': 'string',
                            'enum': [
                                'Min',
                                'Normal',
                                'Max',
                                'Auto'
                              ]
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 44: # V_HVAC_SETPOINT_COOL
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            'minimum':0,
                            'maximum':50,
                            'type': 'number',
                            'unit': 'degree celsius',
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 45: # V_HVAC_SETPOINT_HEAT
                    #self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'LevelProperty',
                            'label': new_description,
                            'minimum':0,
                            'maximum':150,
                            'type': 'number',
                            'unit': 'degree celsius',
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 30:                      # Volt meter
                #self._type.append('MultiLevelSensor')
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        '@type': 'VoltageProperty',
                        'label': new_description,
                        'type': 'number',
                        'unit': 'volt',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 31:                      # Sprinkler
                if new_sub_type == 2: #V_status
                    #self._type.append('OnOffSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

                if new_sub_type == 16: # V_tripped
                    self._type.append('Alarm')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'AlarmProperty',
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 32:                      # Water leak
                if new_sub_type == 15: #V_ARMED
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 16: #V_TRIPPED
                    self._type.append('LeakSensor') 
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LeakProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 33:                       # Sound
                #self._type.append('MultiLevelSensor')        
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        'label': new_description,
                        'type': 'number',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 34:                       # Vibration
                #self._type.append('MultiLevelSensor')        
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        'label': new_description,
                        'type': 'number',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 35:                       # Moisture
                #self._type.append('MultiLevelSensor')        
                if new_sub_type == 37: # V_LEVEL
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 15: # V_ARMED
                    #self._type.append('OnOffSwitch')                       
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 16: # V_TRIPPED                   
                    self._type.append('LeakSensor') 
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LeakProperty',
                            'label': new_description,
                            'type': 'boolean',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 36:                      # S_Info
                if new_sub_type == 47: # V_TEXT
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 38:                      # Gas
                if new_sub_type == 34 or new_sub_type == 35: # V_FLOW & V_VOLUME
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 38:                      # GPS
                if new_sub_type == 49: # V_POSITION
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif new_main_type == 39:                      # Water quality
                if new_sub_type == 2: # V_STATUS
                    #self._type.append('SmartPlug')           
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            #'@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 0: # V_TEMP
                    self._type.append('TemperatureSensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'TemperatureProperty',
                            'label': new_description,
                            'type': 'number',
                            'unit': 'degree celsius',
                            'readOnly': True,
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 51 or new_sub_type == 52 or new_sub_type == 53: # V_PH, V_ORP, V_EC
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                    
            else:
                print("- S_TYPE NOT SUPPORTED YET")
                return

        except Exception as ex:
            print("Device; error creating property: " + str(ex))

 
        try:
            if targetPropertyID in self.properties:
                #self.notify_property_changed(self.properties[targetPropertyID])
                #print("-All properties: " + str(self.get_property_descriptions()))
                try:
                    #self.adapter.handle_device_added(self)
                    if self.adapter.DEBUG:
                        print("---property now exists")
                except Exception as ex:
                    print("Handle_device_added after adding property error: " + str(ex))
                    

            else:
                print("MYSENSORS - THIS V_TYPE IS NOT SUPPORTED YET (OR DOES NOT EXIST)")
                
        except Exception as ex:
            print("Notify after adding property ERROR: " + str(ex))
 

            
        

    
