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
        self._type = []
        self.properties = {}
        #print("device self.properties at init: " + str(self.properties))
        self.connected_notify(True)


    def add_child(self, child, message, sub_type, value):
        #print()
        print("+ DEVICE.ADD_CHILD with child_id: " + str(message.child_id))
        

        # PREFIX
        # First, let's see if there's a prefix. If there is, we should scrape it from the child's value object
        prefix = '' # prefix starts as an empty string.
        try:
            for childSubType in child.values: # The values dictionary can contain multiple items. We loop over each one.
                if childSubType == 43: # If this is a prefix, then don't turn it into a property.
                    print("-Found a prefix")
                    prefix = str(child.values[childSubType])
        except:
            print("Weird: error while looking for a prefix")


        try:
            new_node_id = str(message.node_id)
            new_child_id = str(message.child_id)
            new_sub_type = sub_type
            #new_value = str(value)

            if not child.description:
                print("-Node had no description")
                new_description = ''
            else:
                new_description = child.description

            if is_a_number(value):
                new_value = get_int_or_float(value)
            else:
                new_value = str(value)


            #print("Child object: " + str(child))
            #print("child.type = " + str(child.type)) # Funnily enough, this S_ type is not really needed.
            #print("child_id = " + str(new_child_id))
            #print("sub_type = " + str(new_sub_type))
            #print("property description = " + str(new_description))
            #print("-value = " + str(new_value))

            targetPropertyID = str(new_node_id) + "-" + str(new_child_id) + "-" + str(new_sub_type) # e.g. 2-5-36

            #print("child.type: " + str(child.type))
            #print("new_sub_type: " + str(new_sub_type))

        except Exception as ex:
            print("Error during preparation to add new property: " + str(ex))

        try:
            if child.type == 0:                         # Door
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

            elif child.type == 1:                       # Motion
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

            elif child.type == 2:                       # Smoke
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

            elif child.type == 3:                       # Binary
                if new_sub_type == 2: # V_STATUS
                    self._type.append('SmartPlug')           
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

            elif child.type == 4:                       # Dimmer
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
                if new_sub_type == 3: # V_PERCENTAGE
                    self._type.append('Light')
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
                if new_sub_type == 17: # V_WATT
                    self._type.append('EnergyMonitor')
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

            elif child.type == 5:                       # Window covers (percentage)
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


            elif child.type == 6:                       # Temperature
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

            elif child.type == 7:                       # Humidity
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

            elif child.type == 8:                       # Barometer
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


            elif child.type == 9:                       # Wind
                if new_sub_type == 8: # V_WIND         
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

            elif child.type == 10:                      # Rain
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


            elif child.type == 11:                      # UV level
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

            elif child.type == 12:                      # Weight
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

            elif child.type == 13:                      # Power measuring device, like power meters
                if new_sub_type == 17: # V_WATT
                    self._type.append('EnergyMonitor')
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

            elif child.type == 14:                      # Heater
                if new_sub_type == 0: # V_TEMP
                    self._type.append('MultiLevelSensor')
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
                    self._type.append('MultiLevelSwitch')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'LevelProperty',
                            'label': new_description,
                            'minimum':0,
                            'maximum':150,
                            'type': 'number',
                            'unit': 'degree celsius',
                        },
                    new_value, new_node_id, new_child_id, new_sub_type)

                    # TODO: V_HVAC_FLOW_STATE. Mozilla Gateway has no support for a multiple-buttons type?



                if new_sub_type == 2: #V_status
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


            elif child.type == 15:                      # Distance
                self._type.append('MultiLevelSensor')
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

            elif child.type == 16:                      # Light level
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        'label': new_description,
                        'type': 'number',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)

            elif child.type == 17:                      # Arduino node. This should not be turned into a property.
                pass #          

            elif child.type == 18:                      # Arduino repeater. This should not be turned into a property.
                pass

            elif child.type == 19:                      # Lock                        
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

            elif child.type == 20:                      # Ir sender/receiver device
                pass       

            elif child.type == 21:                      # Water flow
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

            elif child.type == 22:                      # Air quality
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

            elif child.type == 23:                      # CUSTOM
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

            elif child.type == 24:                      # S_DUST
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

            elif child.type == 25:                      # Scene controller
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

            elif child.type == 26:                      # RGB light
                #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
                pass #todo

            elif child.type == 27:                      # RGB light with separate white level
                #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
                pass #todo

            elif child.type == 28:                      # Color sensor
                self.properties[targetPropertyID] = MySensorsProperty(
                    self,
                    targetPropertyID,
                    {
                        'label': new_description,
                        'type': 'string',
                        'readOnly': True,
                    },
                    new_value, new_node_id, new_child_id, new_sub_type)

            elif child.type == 29:                      # Thermostat / HVAC
                pass

            elif child.type == 30:                      # Volt meter
                self._type.append('MultiLevelSensor')
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

            elif child.type == 31:                      # Sprinkler
                if new_sub_type == 2: #V_status
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

                if new_sub_type == 16: # V_tripped
                    self._type.append('BinarySensor')
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'number',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)


            elif child.type == 32:                      # Water leak
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


            elif child.type == 33:                       # Sound
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

            elif child.type == 34:                       # Vibration
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

            elif child.type == 35:                       # Moisture
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
                if new_sub_type == 16: # V_TRIPPED                   
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'boolean',
                            'readOnly': True,
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

            elif child.type == 36:                      # S_Info
                if new_sub_type == 47: # V_TEXT
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

                pass #this should never trigger anyway, strings are handled above.


            elif child.type == 38:                      # Gas
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


            elif child.type == 38:                      # GPS
                if new_sub_type == 49: # V_POSITION
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            'label': new_description,
                            'type': 'string',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)

            elif child.type == 39:                      # Water quality
                if new_sub_type == 2: # V_STATUS
                    self._type.append('SmartPlug')           
                    self.properties[targetPropertyID] = MySensorsProperty(
                        self,
                        targetPropertyID,
                        {
                            '@type': 'OnOffProperty',
                            'label': new_description,
                            'type': 'boolean',
                        },
                        new_value, new_node_id, new_child_id, new_sub_type)
                if new_sub_type == 0: # V_TEMP
                    self._type.append('MultiLevelSensor')
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
            print("Error during calling of create property function from device: " + str(ex))

        #print("targetPropertyID = " + str(targetPropertyID))   
        try:
            #print(str(self.properties[targetPropertyID])) 
            #print("new property in properties dict inside device: " + str(self.properties[targetPropertyID]))
            #print("self.prop.dev: " + str(self.properties[targetPropertyID]))
            self.notify_property_changed(self.properties[targetPropertyID])
            #print("-All properties: " + str(self.get_property_descriptions()))
        except Exception as ex:
            print("notify after adding property error: " + str(ex))
        
        try:
            self.adapter.handle_device_added(self)
            #print("-All properties: " + str(self.get_property_descriptions()))
        except Exception as ex:
            print("Handle_device_added after adding property error: " + str(ex))
    
