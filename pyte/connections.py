"""
.. module:: connections
    :platforms: all
    :synopsis:

.. moduleauthor:: Francesco Witte <francesco.witte@hs-flensburg.de>
"""

import numpy as np
import pandas as pd

from ppsim.helpers import MyConnectionError
from ppsim.components import components as cmp


class connection:
    """
    class connection

    creates connection between two components

    .. note::
    """
    def __init__(self, comp1, outlet_id, comp2, inlet_id, **kwargs):
        """
        object initialisation
            - check argument consistency
            - set attributes to specified values

        :param comp1: connections source
        :type comp1: ppsim.components object
        :param outlet_id: outlet id at the connections source
        :type outlet_id: str
        :param comp2: connections target
        :type comp2: ppsim.components object
        :param inlet_id: inlet id at the connections target
        :type inlet_id: str

        allowed keywords in kwargs (also see connections.attr()):
            - m, m0
            - p, p0
            - h, h0
            - T
            - x
            - fluid

        :returns: no return value
        :raises: - :code:`TypeError`, if comp1 and comp2 are not of type
                   components
                 - :code:`ValueError`, if comp1 and comp2 are the same object
                 - :code:`ValueError`, if outlet_id or inlet_id are not allowed
                   for ids for comp1 or comp2

        example
            .. code-block:: python
                conn = connections(turbine, 'out1', condenser, 'in1', m=10,
                p=0.05)

        creates component from turbine to condenser (hot side inlet) and sets
        values for mass flow and pressure
        """

        # check input parameters
        if not (isinstance(comp1, cmp.component) and
                isinstance(comp2, cmp.component)):
            msg = ('Error creating connection.'
                   'Check if comp1, comp2 are of type component.')
            raise TypeError(msg)

        if comp1 == comp2:
            msg = ('Error creating connection. '
                   'Can\'t connect component to itself.')
            raise ValueError(msg)

        if outlet_id not in comp1.outlets():
            msg = ('Error creating connection. '
                   'Specified oulet_id is not valid for component ' +
                   comp1.component() + '. '
                   'Valid ids are: ' + str(comp1.outlets()) + '.')
            raise ValueError(msg)

        if inlet_id not in comp2.inlets():
            msg = ('Error creating connection. '
                   'Specified inlet_id is not valid for component ' +
                   comp2.component() + '. '
                   'Valid ids are: ' + str(comp2.inlets()) + '.')
            raise ValueError(msg)

        # set default values
        self.s = comp1
        self.s_id = outlet_id
        self.t = comp2
        self.t_id = inlet_id
        self.m = kwargs.get('m', np.nan)
        self.p = kwargs.get('p', np.nan)
        self.h = kwargs.get('h', np.nan)
        self.T = kwargs.get('T', np.nan)
        self.x = kwargs.get('x', np.nan)

        self.fluid = kwargs.get('fluid', {})
        self.fluid_set = {}

        self.m0 = kwargs.get('m0', 1)
        self.p0 = kwargs.get('p0', np.nan)
        self.h0 = kwargs.get('h0', np.nan)

        self.m_set = False
        self.p_set = False
        self.h_set = False
        self.T_set = False
        self.x_set = False

        # setters for specified values
        for key in kwargs:
            if (isinstance(kwargs[key], float) or
                isinstance(kwargs[key], int) or
                isinstance(kwargs[key], ref)):
                self.__dict__.update({key + '_set': True})
            if key == 'fluid':
                for fluid in sorted(kwargs[key].keys()):
                    self.fluid_set[fluid] = True

        if self.m_set and not isinstance(self.m, ref):
            self.m0 = self.m
        if self.p_set and not isinstance(self.p, ref):
            self.p0 = self.p
        if self.h_set and not isinstance(self.h, ref):
            self.h0 = self.h

    def set_attr(self, **kwargs):
        """
        sets, resets or unsets attributes of a connection, for the keyword
        arguments, return values and errors see object initialisation
        """
        invalid_keys = np.array([])
        for key in kwargs:
            if key not in self.attr():
                invalid_keys = np.append(invalid_keys, key)
            if (isinstance(kwargs[key], float) or
                isinstance(kwargs[key], int) or
                isinstance(kwargs[key], ref)):
                self.__dict__.update({key: kwargs[key]})
                if isinstance(kwargs[key], ref):
                    self.__dict__.update({key + '_set': True})
                else:
                    if np.isnan(kwargs[key]):
                        self.__dict__.update({key + '_set': False})
                    else:
                        self.__dict__.update({key + '_set': True})

            if key == 'fluid':
                for fluid, x in kwargs[key].items():
                    self.fluid[fluid] = x
                    self.fluid_set[fluid] = True

        if len(invalid_keys) > 0:
            print(invalid_keys, 'are invalid attributes.',
                  'Available attributes for flow are:', self.attr(), '.')

    def get_attr(self, key):
        """
        get the value of a connection attribute

        :param key: attribute to return its value
        :type key: str
        :returns:
            - :code:`self.__dict__[key]` if object has attribute key
            - :code:`None` if object has no attribute key
        """
        if key in self.__dict__:
            return self.__dict__[key]
        else:
            print(self.connection(), ' has no attribute \"', key, '\"')
            return None

    def attr(self):
        """
        get the list of attributes allowed for a connection object

        :returns: list object
        """
        return ['m', 'p', 'h', 'T', 'x', 'm0', 'p0', 'h0', 'fluid']

    def as_list(self):
        """
        create a list containing the connections fluid information

        :returns: :code:`[mass flow, pressure, enthalpy, fluid vector]`
        """
        return [self.m, self.p, self.h, self.fluid]


class bus:
    """
    establish power connection between turbines, pumps, heat exchanger
    """

    def __init__(self, name,  ** kwargs):
        self.name = name
        self.comps = pd.DataFrame(columns=['factor'])
        self.P = np.nan
        self.P_set = False
        if 'P' in kwargs:
            self.P = kwargs['P']
            self.P_set = True

    def add_comp(self,  * args):
        """
        add component to bus
        """
        for c in args:
            if isinstance(c, list):
                if len(c) == 2:
                    if c[1] in (-1, 1):
                        self.comps.loc[c[0]] = [c[1]]
                        if not self.check_comp(c[0]):
                            self.comps = self.comps[: - 1]
                    else:
                        raise ValueError('Factor must be 1 or  - 1.')
                else:
                    msg = 'Provide parameters as follows: [component, factor].'
                    raise MyConnectionError(msg)
            else:
                msg = 'Provide parameters as follows: [component, factor].'
                raise MyConnectionError(msg)

    def check_comp(self, comp):
        """
        check component
        """
        for c in self.comps.index:
            if type(comp) != type(c):
                if (type(comp).__bases__[0] == type(c).__bases__[0] and
                    type(comp).__bases__[0] == cmp.component):

                    if type(c).__bases__[0] == cmp.component:
                        msg = ('Error adding component to power bus. '
                               'This bus accepts components of type ' +
                               str(type(c)) + '.')
                        raise TypeError(msg)
                    else:
                        msg = ('Error adding component to power bus. '
                               'This bus accepts components of type ' +
                               str(type(c).__bases__[0]) + '.')
                        raise TypeError(msg)

                return False

        return True


class ref:
    """
    class reference

    creates reference object for network parametetrisation
    """
    def __init__(self, ref_obj, factor, delta):
        """
        method __init__

        object initialisation
        --------
        arguments
            ref_obj: ppsim.connection
                connection to be referenced
            factor: float
                factor for referenced value
            delta: float
                delta for referenced value
        --------
        returns
            None
        """
        if not isinstance(ref_obj, connection):
            msg = 'First parameter must be object of type connection.'
            raise TypeError(msg)

        if not (isinstance(factor, int) or isinstance(factor, float)):
            msg = 'Second parameter must be of type int or float.'
            raise TypeError(msg)

        if not (isinstance(delta, int) or isinstance(delta, float)):
            msg = 'Thrid parameter must be of type int or float.'
            raise TypeError(msg)

        self.obj = ref_obj
        self.f = factor
        self.d = delta
