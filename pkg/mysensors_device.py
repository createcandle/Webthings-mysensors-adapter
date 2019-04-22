"""MySensors adapter for Mozilla WebThings Gateway."""


import threading
import time
import mysensors.mysensors as mysensors

from gateway_addon import Device
from .mysensors_property import MySensorsProperty #, MySensorsTemperatureProperty
from .util import pretty, is_a_number



class MySensorsDevice(Device):
    """MySensors device type."""

    def __init__(self, adapter, _id, node):
        """
        Initialize the object.

        adapter -- the Adapter managing this device
        _id -- ID of this device
        node -- The MySensors Node object to initialize from
        index -- index inside parent device
        """
        
        print("Device init: " + str(node.sketch_name))
        Device.__init__(self, adapter, _id)
        
        self.adapter = adapter
        self.id = str(_id)
        self._id = str(_id)
        self.node = node
        self.name = node.sketch_name
        self.description = node.sketch_name
        self._type = []
        self.properties = {} # this should already be initialised?
        #print("device self.properties at init: " + str(self.properties))

        for childIndex in self.node.children:
            
            child = self.node.children[childIndex]
            #print(str(child))
            
            node_child_id = str(child.id) # we need a unique ID to create a property for each MySensors Child (and then each subtype of that child)
            
            #print("child id = " + node_child_id)
            #print("child type = " + str(child.type))
            #print("desc = " + str(child.description))
            #print("val = " + str(child.values))
            
            
            if not child.values: # If the value field is empty then just skip it.
                continue
            
            
            for childSubType in child.values: # The values dictionary can contain multiple items. We loop over each one.
                #print("childSubType " + str(childSubType)) # The index (id) of the value in the values dictionary. This is the mysensors subtype.
                
                node_child_id = node_child_id + "-" + str(childSubType) # Generating a unique name, e.g. 5-2 for child 5 with subtype 2.
                
                
                if not is_a_number(child.values[childSubType]): # if the actual value is a string, we create a new string property.
                    ''' # still waiting to figure out how a string can be passed to the gateway (which property should be used)
                    realValue = str(child.values[childSubType])
                    
                    if child.type == 36:                       # MySensors has an 'info' child type, which is a string.
                        self.properties[child.id] = MySensorsProperty(
                            self,
                            'InfoProperty',
                            {
                                '@type': 'LevelProperty',
                                'label': child.description,
                                'type': 'string',
                            },
                            realValue)
                    else:                                       # sometimes a child can also have a string value attached, such as a barometer child that has both the air pressure in hPa as well as a weather prediction.
                        pass # put something similar as above here.
                    
                    '''
                    pass
                
                else:                                           # The child's value is a number. Let's create a property for it.
                    realValue = float(child.values[childSubType])
                    print("realval = " + str(realValue))
                    print("self.adapter = " + str(self.adapter))

                    if child.type == 0:                         # Door
                        if childSubType == 16: # V_TRIPPED
                            self._type.append('DoorSensor')                       
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OpenProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                            
                        if childSubType == 15: # V_ARMED
                            self._type.append('OnOffSwitch')                       
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                            
                    elif child.type == 1:                       # Motion
                        if childSubType == 16: # V_TRIPPED
                            self._type.append('MotionSensor')   
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'MotionProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        if childSubType == 15: # V_ARMED
                            self._type.append('OnOffSwitch')                       
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        
                    elif child.type == 2:                       # Smoke
                        if childSubType == 16: # V_TRIPPED
                            self._type.append('Alarm')           
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'AlarmProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        if childSubType == 15: # V_ARMED
                            self._type.append('OnOffSwitch')                       
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        
                    elif child.type == 3:                       # Binary
                        if childSubType == 2: # V_STATUS
                            self._type.append('SmartPlug')           
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        if childSubType == 17: # V_WATT (power meter)          
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'InstantaneousPowerProperty',
                                    'label': child.description,
                                    'type': 'number',
                                    'unit': 'watt',
                                },
                                realValue)
                        
                    elif child.type == 4:                       # Dimmer
                        if childSubType == 2: # V_STATUS
                            self._type.append('OnOffSwitch')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        
                        if childSubType == 3: # V_PERCENTAGE
                            self._type.append('Light')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'BrightnessProperty',
                                    'label': child.description,
                                    'minimum': 0,
                                    'maximum': 100,
                                    'type': 'number',
                                    'unit': 'percent',
                                },
                                realValue)
                        
                    elif child.type == 5:                       # Window covers (percentage)
                        if childSubType == 3: # V_PERCENTAGE
                            self._type.append('MultiLevelSwitch')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'LevelProperty',
                                    'label': child.description,
                                    'minimum': 0,
                                    'maximum': 100,
                                    'type': 'number',
                                    'unit': 'percent',
                                },
                                realValue)
                        
                        
                    elif child.type == 6:                       # Temperature
                        if childSubType == 0: # V_TEMP
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'TemperatureProperty',
                                    'label': child.description,
                                    'type': 'number',
                                    'unit': 'degree celcius',
                                    'readOnly': True,
                                },
                                realValue)

                    elif child.type == 7:                       # Humidity
                        if childSubType == 1: # V_HUM
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'LevelProperty',
                                    'label': child.description,
                                    'minimum': 0,
                                    'maximum': 100,
                                    'type': 'number',
                                    'unit': 'percent',
                                    'readOnly': True,
                                },
                                realValue)

                    elif child.type == 8:                       # Barometer
                        if childSubType == 4: # V_PRESSURE (atmospheric pressure)
                            self._type.append('MultiLevelSensor')                 
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'LevelProperty',
                                    'label': child.description,
                                    'minimum': 900,
                                    'maximum': 1100,
                                    'type': 'number',
                                    'unit': 'hPa',
                                    'readOnly': True,
                                },
                                realValue)
                        if childSubType == 5: # V_FORECAST (weather prediction)
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'string',
                                    'readOnly': True,
                                },
                                realValue)


                    elif child.type == 9:                       # Wind
                        if childSubType == 8: # V_WIND
                            self._type.append('MultiLevelSensor')             
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                        if childSubType == 10: # V_DIRECTION (of wind)
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'string',
                                    #'readOnly': True,
                                },
                                realValue)
                            
                    elif child.type == 10:                      # Rain
                        if childSubType == 6: # V_RAIN
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                        if childSubType == 7: # V_RAINRATE
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                        
                        
                    elif child.type == 11:                      # UV level
                        if childSubType == 11: # V_UV
                            self._type.append('MultiLevelSensor') 
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                    elif child.type == 12:                      # Weight
                        if childSubType == 12: # V_WEIGHT
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                    
                    elif child.type == 13:                      # Power measuring device, like power meters
                        self._type.append('EnergyMonitor')
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                '@type': 'InstantaneousPowerProperty',
                                'label': child.description,
                                'type': 'number',
                                'unit': 'watt',
                                #'readOnly': True,
                            },
                            realValue)
                        
                    elif child.type == 14:                      # Heater
                        pass
                    
                    elif child.type == 15:                      # Distance
                        self._type.append('MultiLevelSensor')
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'number',
                                #'readOnly': True,
                            },
                            realValue)
                        
                    elif child.type == 16:                      # Light level
                        self._type.append('MultiLevelSensor')
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'number',
                                #'readOnly': True,
                            },
                            realValue)
                        
                    elif child.type == 17:                      # Arduino node
                        pass                 
                    
                    elif child.type == 18:                      # Arduino repeater
                        pass
                    
                    elif child.type == 19:                      # Scene controller device
                        self._type.append('OnOffSwitch')    
                        
                    elif child.type == 20:                      # Ir sender/receiver device
                        pass       
                    
                    elif child.type == 22:                      # Air quality
                        if childSubType == 37: # V_LEVEL
                            self._type.append('MultiLevelSensor')
                            self.properties[node_child_id] = MySensorsProperty( #def __init__(self, device, name, description, value):
                                self,
                                node_child_id,
                                {
                                    '@type': 'LevelProperty',
                                    'label': child.description,
                                    'minimum': 0,
                                    'maximum': 10000,
                                    'type': 'number',
                                    'unit': 'ppm',
                                    #'readOnly': True,
                                },
                                realValue)

                    elif child.type == 25:                      # Scene controller
                        self._type.append('OnOffSwitch')
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                '@type': 'OnOffProperty',
                                'label': child.description,
                                'type': 'boolean',
                            },
                            realValue)
                        
                    elif child.type == 26:                      # RGB light
                        #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
                        pass
                    
                    elif child.type == 27:                      # RGB light with separate white level
                        #self._type.append(['OnOffSwitch', 'Light', 'ColorControl'])
                        pass
                    
                    elif child.type == 28:                      # Color sensor
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'string',
                                #'readOnly': True,
                            },
                            realValue)
                        
                    elif child.type == 29:                      # Thermostat / HVAC
                        pass
                    
                    elif child.type == 30:                      # Volt meter
                        self._type.append('MultiLevelSensor')
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                '@type': 'VoltageProperty',
                                'label': child.description,
                                'type': 'number',
                                'unit': 'volt',
                            },
                            realValue)
                        
                    elif child.type == 31:                      # Sprinkler
                        if childSubType == 2: #V_status
                            self._type.append('OnOffSwitch')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    '@type': 'OnOffProperty',
                                    'label': child.description,
                                    'type': 'boolean',
                                },
                                realValue)
                        
                        if childSubType == 16: # V_tripped
                            self._type.append('BinarySensor')
                            self.properties[node_child_id] = MySensorsProperty(
                                self,
                                node_child_id,
                                {
                                    'label': child.description,
                                    'type': 'number',
                                    #'readOnly': True,
                                },
                                realValue)
                        
                        
                    elif child.type == 32:                      # Water leak
                        self._type.append('LeakSensor') 
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                '@type': 'LeakProperty',
                                'label': child.description,
                                'type': 'boolean',
                            },
                            realValue)
                        
                        
                    elif child.type == 33:                       # Sound
                        self._type.append('MultiLevelSensor')        
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'number',
                                #'readOnly': True,
                            },
                            realValue)

                    elif child.type == 34:                       # Vibration
                        self._type.append('MultiLevelSensor')        
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'number',
                                #'readOnly': True,
                            },
                            realValue)
                        
                    elif child.type == 35:                       # Moisture
                        self._type.append('MultiLevelSensor')        
                        self.properties[node_child_id] = MySensorsProperty(
                            self,
                            node_child_id,
                            {
                                'label': child.description,
                                'type': 'number',
                                #'readOnly': True,
                            },
                            realValue)
                        
                        
                    elif child.type == 36:                      # String
                        pass
                        '''
                        self.properties[child.id] = MySensorsProperty(
                            self,
                            'TemperatureProperty',
                            {
                                '@type': 'LevelProperty',
                                'label': child.description,
                                'type': 'string',
                            },
                            realValue)
                        '''
                    elif child.type == 37:                      # GPS
                        pass            
                    elif child.type == 38:                      # Water quality
                        pass
                    else:
                        pass