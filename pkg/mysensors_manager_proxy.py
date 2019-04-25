"""MySensors adapter for Mozilla WebThings Gateway."""

import time
import mysensors.mysensors as mysensors

from threading import Timer
from gateway_addon import AddonManagerProxy, Adapter, Database
from .mysensors_adapter import MySensorsAdapter
from .util import pretty, is_a_number

_TIMEOUT = 3


class MySensorsManagerProxy(AddonManagerProxy):
    """Adapter for TP-Link smart home devices."""

    def __init__(self, verbose=True):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """
        print("initialising AddonManagerProxy from class")
        
        self.name = self.__class__.__name__
        AddonManagerProxy.__init__(self, 'mysensors-manager-proxy', verbose=verbose)

            