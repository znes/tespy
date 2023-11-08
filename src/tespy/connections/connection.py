# -*- coding: utf-8
"""Module of class Connection and class Ref.


This file is part of project TESPy (github.com/oemof/tespy). It's copyrighted
by the contributors recorded in the version control history of the file,
available from its original location tespy/connections/connection.py

SPDX-License-Identifier: MIT
"""

from collections import OrderedDict

import numpy as np

from tespy.components.component import Component
from tespy.tools import fluid_properties as fp
from tespy.tools import logger
from tespy.tools.data_containers import DataContainer as dc
from tespy.tools.data_containers import FluidComposition as dc_flu
from tespy.tools.data_containers import FluidProperties as dc_prop
from tespy.tools.data_containers import ReferencedFluidProperties as dc_ref
from tespy.tools.data_containers import SimpleDataContainer as dc_simple
from tespy.tools.fluid_properties import CoolPropWrapper
from tespy.tools.fluid_properties import Q_mix_ph
from tespy.tools.fluid_properties import T_mix_ph
from tespy.tools.fluid_properties import T_sat_p
from tespy.tools.fluid_properties import dh_mix_dpQ
from tespy.tools.fluid_properties import dT_mix_dph
from tespy.tools.fluid_properties import dT_mix_pdh
from tespy.tools.fluid_properties import dT_sat_dp
from tespy.tools.fluid_properties import dv_mix_dph
from tespy.tools.fluid_properties import dv_mix_pdh
from tespy.tools.fluid_properties import h_mix_pQ
from tespy.tools.fluid_properties import h_mix_pT
from tespy.tools.fluid_properties import s_mix_ph
from tespy.tools.fluid_properties import v_mix_ph
from tespy.tools.fluid_properties import viscosity_mix_ph
from tespy.tools.fluid_properties.functions import dT_mix_ph_dfluid
from tespy.tools.fluid_properties.functions import p_sat_T
from tespy.tools.fluid_properties.helpers import get_number_of_fluids
from tespy.tools.global_vars import ERR
from tespy.tools.global_vars import fluid_property_data as fpd
from tespy.tools.helpers import TESPyConnectionError
from tespy.tools.helpers import TESPyNetworkError
from tespy.tools.helpers import convert_from_SI


class Connection:
    r"""
    Class connection is the container for fluid properties between components.

    Parameters
    ----------
    m : float, tespy.connections.connection.Ref
        Mass flow specification.

    m0 : float
        Starting value specification for mass flow.

    p : float, tespy.connections.connection.Ref
        Pressure specification.

    p0 : float
        Starting value specification for pressure.

    h : float, tespy.connections.connection.Ref
        Enthalpy specification.

    h0 : float
        Starting value specification for enthalpy.

    fluid : dict
        Fluid compostition specification.

    fluid0 : dict
        Starting value specification for fluid compostition.

    fluid_balance : boolean
        Fluid balance equation specification.

    x : float
        Gas phase mass fraction specification.

    T : float, tespy.connections.connection.Ref
        Temperature specification.

    Td_bp : float
        Temperature difference to boiling point at pressure corresponding
        pressure of this connection in K.

    v : float
        Volumetric flow specification.

    state : str
        State of the pure fluid on this connection: liquid ('l') or gaseous
        ('g').

    design : list
        List containing design parameters (stated as string).

    offdesign : list
        List containing offdesign parameters (stated as string).

    design_path : str
        Path to individual design case for this connection.

    local_offdesign : boolean
        Treat this connection in offdesign mode in a design calculation.

    local_design : boolean
        Treat this connection in design mode in an offdesign calculation.

    printout : boolean
        Include this connection in the network's results printout.

    label : str
        Label of the connection. The default value is:
        :code:`'source:source_id_target:target_id'`.

    Note
    ----
    - The fluid balance parameter applies a balancing of the fluid vector on
      the specified conntion to 100 %. For example, you have four fluid
      components (a, b, c and d) in your vector, you set two of them
      (a and b) and want the other two (components c and d) to be a result of
      your calculation. If you set this parameter to True, the equation
      (0 = 1 - a - b - c - d) will be applied.

    - The specification of values for design and/or offdesign is used for
      automatic switch from design to offdesign calculation: All parameters
      given in 'design', e.g. :code:`design=['T', 'p']`, are unset in any
      offdesign calculation, parameters given in 'offdesign' are set for
      offdesign calculation.

    Example
    -------
    This example shows how to create connections and specify parameters. First
    create the required components and connect them in the next step. After
    that, it is possible specify parameters with the :code:`set_attr` method.

    >>> from tespy.components import Sink, Source
    >>> from tespy.connections import Connection, Ref
    >>> from tespy.tools import FluidComposition as dc_flu
    >>> from tespy.tools import FluidProperties as dc_prop
    >>> import numpy as np
    >>> so1 = Source('source1')
    >>> so2 = Source('source2')
    >>> si1 = Sink('sink1')
    >>> si2 = Sink('sink2')
    >>> so_si1 = Connection(so1, 'out1', si1, 'in1', label='connection 1')
    >>> so_si2 = Connection(so2, 'out1', si2, 'in1')
    >>> so_si1.label
    'connection 1'
    >>> so_si2.label
    'source2:out1_sink2:in1'

    There are different ways of setting parameters on connections: Specify

    - a numeric value  (for attributes mass flow, pressure and enthalpy)
    - a numeric starting value (for attributes mass flow, pressure and
      enthalpy)
    - a dictionary (for attributes fluid and fluid0)
    - a boolean value (for attributes fluid_balance, local_design,
      local_offdesign).
    - a referenced value (mass flow, pressure, temperature, enthalpy).
    - numpy.nan or None (unsetting a value).
    - a string (for attributes design_path and state).
    - a list (for attributes design and offdesign).

    >>> so_si1.set_attr(v=0.012, m0=10, p=5, h=400, fluid={'H2O': 1})
    >>> so_si2.set_attr(m=Ref(so_si1, 2, -5), h0=700, T=200,
    ... fluid={'N2': 1}, fluid_balance=True,
    ... design=['T'], offdesign=['m', 'v'])

    The set_attr method automatically converts your input in data_container
    information.

    >>> type(so_si1.v)
    <class 'tespy.tools.data_containers.FluidProperties'>
    >>> type(so_si1.fluid)
    <class 'tespy.tools.data_containers.FluidComposition'>

    If you want get a spcific value use the logic: connection.property.*.
    Aditionally, it is possible to use the :code:`get_attr` method.

    >>> so_si1.m.val0
    10
    >>> so_si1.m.is_set
    False
    >>> so_si1.m.get_attr('is_set')
    False
    >>> type(so_si2.m_ref.ref)
    <class 'tespy.connections.connection.Ref'>
    >>> so_si2.fluid.get_attr('balance')
    True
    >>> so_si2.m_ref.ref.get_attr('delta')
    -5
    >>> so_si2.m_ref.is_set
    True
    >>> type(so_si2.m_ref.ref.get_attr('obj'))
    <class 'tespy.connections.connection.Connection'>

    Unset the specified temperature and specify temperature difference to
    boiling point instead.

    >>> so_si2.T.is_set
    True
    >>> so_si2.set_attr(Td_bp=5, T=None)
    >>> so_si2.T.is_set
    False
    >>> so_si2.Td_bp.val
    5
    >>> so_si2.set_attr(Td_bp=None)
    >>> so_si2.Td_bp.is_set
    False

    Specify the state keyword: The fluid will be forced to liquid or gaseous
    state in this case.

    >>> so_si2.set_attr(state='l')
    >>> so_si2.state.is_set
    True
    >>> so_si2.set_attr(state=None)
    >>> so_si2.state.is_set
    False
    >>> so_si2.set_attr(state='g')
    >>> so_si2.state.is_set
    True
    >>> so_si2.set_attr(state=None)
    >>> so_si2.state.is_set
    False
    """

    def __init__(self, source, outlet_id, target, inlet_id,
                 label=None, **kwargs):

        self._check_types(source, target)
        self._check_self_connect(source, target)
        self._check_connector_id(source, outlet_id, source.outlets())
        self._check_connector_id(target, inlet_id, target.inlets())

        self.label = f"{source.label}:{outlet_id}_{target.label}:{inlet_id}"
        if label is not None:
            self.label = label
            if not isinstance(label, str):
                msg = "Please provide the label as string."
                logger.error(msg)
                raise TypeError(msg)

        # set specified values
        self.source = source
        self.source_id = outlet_id
        self.target = target
        self.target_id = inlet_id

        # defaults
        self.new_design = True
        self.design_path = None
        self.design = []
        self.offdesign = []
        self.local_design = False
        self.local_offdesign = False
        self.printout = True

        self.force_state = None
        self.good_starting_values = None

        # set default values for kwargs
        self.property_data = self.get_parameters()
        self.parameters = {
            k: v for k, v in self.get_parameters().items()
            if (isinstance(v, dc_prop) or isinstance(v, dc_ref)) and v.func is not None
        }
        self.state = dc_simple()
        self.property_data0 = [x + '0' for x in self.property_data.keys()]
        self.__dict__.update(self.property_data)
        self.mixing_rule = None
        msg = (
            f"Created connection from {self.source.label} ({self.source_id}) "
            f"to {self.target.label} ({self.target_id})."
        )
        logger.debug(msg)

        self.set_attr(**kwargs)

    def _check_types(self, source, target):
        # check input parameters
        if not (isinstance(source, Component) and
                isinstance(target, Component)):
            msg = (
                "Error creating connection. Check if source and target are "
                "tespy.components."
            )
            logger.error(msg)
            raise TypeError(msg)

    def _check_self_connect(self, source, target):
        if source == target:
            msg = (
                "Error creating connection. Cannot connect component "
                f"{source.label} to itself."
            )
            logger.error(msg)
            raise TESPyConnectionError(msg)

    def _check_connector_id(self, component, connector_id, connecter_locations):
        if connector_id not in connecter_locations:
            msg = (
                "Error creating connection. Specified connector for "
                f"{component.label} ({connector_id} is not available. Choose "
                f"from " + ", ".join(connecter_locations) + "."
            )
            logger.error(msg)
            raise ValueError(msg)


    def set_attr(self, **kwargs):
        r"""
        Set, reset or unset attributes of a connection.

        Parameters
        ----------
        m : float, tespy.connections.connection.Ref
            Mass flow specification.

        m0 : float
            Starting value specification for mass flow.

        p : float, tespy.connections.connection.Ref
            Pressure specification.

        p0 : float
            Starting value specification for pressure.

        h : float, tespy.connections.connection.Ref
            Enthalpy specification.

        h0 : float
            Starting value specification for enthalpy.

        fluid : dict
            Fluid composition specification.

        fluid0 : dict
            Starting value specification for fluid composition.

        fluid_balance : boolean
            Fluid balance equation specification.

        x : float
            Gas phase mass fraction specification.

        T : float, tespy.connections.connection.Ref
            Temperature specification.

        Td_bp : float
            Temperature difference to boiling point at pressure corresponding
            pressure of this connection in K.

        v : float
            Volumetric flow specification.

        state : str
            State of the pure fluid on this connection: liquid ('l') or gaseous
            ('g').

        design : list
            List containing design parameters (stated as string).

        offdesign : list
            List containing offdesign parameters (stated as string).

        design_path : str
            Path to individual design case for this connection.

        local_offdesign : boolean
            Treat this connection in offdesign mode in a design calculation.

        local_design : boolean
            Treat this connection in design mode in an offdesign calculation.

        printout : boolean
            Include this connection in the network's results printout.

        Note
        ----
        - The fluid balance parameter applies a balancing of the fluid vector
          on the specified connection to 100 %. For example, you have four
          fluid components (a, b, c and d) in your vector, you set two of them
          (a and b) and want the other two (components c and d) to be a result
          of your calculation. If you set this parameter to True, the equation
          (0 = 1 - a - b - c - d) will be applied.
        - The specification of values for design and/or offdesign is used for
          automatic switch from design to offdesign calculation: All parameters
          given in 'design', e.g. :code:`design=['T', 'p']`, are unset in any
          offdesign calculation, parameters given in 'offdesign' are set for
          offdesign calculation.
        - The property state is applied on pure fluids only. If you specify the
          desired state of the fluid at a connection the convergence check will
          adjust the enthalpy values of that connection for the first
          iterations in order to meet the state requirement.
        """
        # set specified values
        for key in kwargs:
            if key == 'label':
                msg = 'Label can only be specified on instance creation.'
                logger.error(msg)
                raise TESPyConnectionError(msg)
            elif 'fluid' in key:
                self._fluid_specification(key, kwargs[key])

            elif key in self.property_data or key in self.property_data0:
                self._parameter_specification(key, kwargs[key])

            elif key == 'state':
                if kwargs[key] in ['l', 'g']:
                    self.state.set_attr(val=kwargs[key], is_set=True)
                elif kwargs[key] is None:
                    self.state.set_attr(is_set=False)
                else:
                    msg = (
                        'Keyword argument "state" must either be '
                        '"l" or "g" or be None.'
                    )
                    logger.error(msg)
                    raise TypeError(msg)

            # design/offdesign parameter list
            elif key in ['design', 'offdesign']:
                if not isinstance(kwargs[key], list):
                    msg = f"Please provide the {key} parameters as list!"
                    logger.error(msg)
                    raise TypeError(msg)
                elif set(kwargs[key]).issubset(self.property_data.keys()):
                    self.__dict__.update({key: kwargs[key]})
                else:
                    params = ', '.join(self.property_data.keys())
                    msg = (
                        "Available parameters for (off-)design specification "
                        f"are: {params}."
                    )
                    logger.error(msg)
                    raise ValueError(msg)

            # design path
            elif key == 'design_path':
                if isinstance(kwargs[key], str) or kwargs[key] is None:
                    self.__dict__.update({key: kwargs[key]})
                    self.new_design = True
                else:
                    msg = "Provide the a string or None for 'design_path'."
                    logger.error(msg)
                    raise TypeError(msg)

            # other boolean keywords
            elif key in ['printout', 'local_design', 'local_offdesign']:
                if not isinstance(kwargs[key], bool):
                    msg = ('Please provide the ' + key + ' as boolean.')
                    logger.error(msg)
                    raise TypeError(msg)
                else:
                    self.__dict__.update({key: kwargs[key]})

            elif key == "mixing_rule":
                self.mixing_rule = kwargs[key]

            elif key == "force_state":
                self.force_state = kwargs[key]
                
            elif key == "good_starting_values":
                self.good_starting_values = kwargs[key]
                
            # invalid keyword
            else:
                msg = 'Connection has no attribute ' + key + '.'
                logger.error(msg)
                raise KeyError(msg)

    def _fluid_specification(self, key, value):

        self._check_fluid_datatypes(key, value)

        if key == "fluid":
            for fluid, fraction in value.items():
                if "::" in fluid:
                    back_end, fluid = fluid.split("::")
                else:
                    back_end = None

                if fraction is None:
                    if fluid in self.fluid.is_set:
                        self.fluid.is_set.remove(fluid)
                    self.fluid.is_var.add(fluid)
                else:
                    self.fluid.val[fluid] = fraction
                    self.fluid.is_set.add(fluid)
                    if fluid in self.fluid.is_var:
                        self.fluid.is_var.remove(fluid)
                    self.fluid.back_end[fluid] = back_end

        elif key == "fluid0":
            self.fluid.val0.update(value)

        elif key == "fluid_engines":
            self.fluid.engine = value

        elif key == "fluid_balance":
            self.fluid.set_attr(balance=value)

        else:
            msg = f"Connections do not have an attribute named {key}"
            logger.error(msg)
            raise KeyError(msg)

    def _check_fluid_datatypes(self, key, value):
        if key == "fluid_balance":
            if not isinstance(value, bool):
                msg = "Datatype for 'fluid_balance' must be boolean."
                logger.error(msg)
                raise TypeError(msg)
        else:
            if not isinstance(value, dict):
                msg = "Datatype for fluid vector specification must be dict."
                logger.error(msg)
                raise TypeError(msg)

    def _parameter_specification(self, key, value):
        try:
            float(value)
            is_numeric = True
        except (TypeError, ValueError):
            is_numeric = False

        if value is None:
            self.get_attr(key).set_attr(is_set=False)
            if f"{key}_ref" in self.property_data:
                self.get_attr(key).set_attr(is_set=False)
            if key in ["m", "p", "h"]:
                self.get_attr(key).is_var = True

        elif is_numeric:
            # value specification
            if key in self.property_data:
                self.get_attr(key).set_attr(is_set=True, val=value)
                if key in ["m", "p", "h"]:
                    self.get_attr(key).is_var = False
            # starting value specification
            else:
                self.get_attr(key.replace('0', '')).set_attr(val0=value)

        # reference object
        elif isinstance(value, Ref):
            if f"{key}_ref" not in self.property_data:
                msg = f"Referencing {key} is not implemented."
                logger.error(msg)
                raise NotImplementedError(msg)
            else:
                self.get_attr(f"{key}_ref").set_attr(ref=value)
                self.get_attr(f"{key}_ref").set_attr(is_set=True)

        # invalid datatype for keyword
        else:
            msg = f"Wrong datatype for keyword argument {key}."
            logger.error(msg)
            raise TypeError(msg)

    def get_attr(self, key):
        r"""
        Get the value of a connection's attribute.

        Parameters
        ----------
        key : str
            The attribute you want to retrieve.

        Returns
        -------
        out :
            Specified attribute.
        """
        if key in self.__dict__:
            return self.__dict__[key]
        else:
            msg = 'Connection has no attribute \"' + key + '\".'
            logger.error(msg)
            raise KeyError(msg)

    def serialize(self):
        export = {}
        export.update({"source": self.source.label})
        export.update({"target": self.target.label})
        for k in self._serializable():
            export.update({k: self.get_attr(k)})
        for k in self.property_data:
            data = self.get_attr(k)
            export.update({k: data.serialize()})

        export.update({"state": self.state.serialize()})

        return {self.label: export}

    @staticmethod
    def _serializable():
        return [
            "source_id", "target_id",
            "design_path", "design", "offdesign", "local_design", "local_design",
            "printout", "mixing_rule","good_starting_values","force_state"
        ]

    def _create_fluid_wrapper(self):
        for fluid in self.fluid.val:
            if fluid in self.fluid.wrapper:
                continue
            if fluid not in self.fluid.engine:
                self.fluid.engine[fluid] = CoolPropWrapper

            back_end = None
            if fluid in self.fluid.back_end:
                back_end = self.fluid.back_end[fluid]
            else:
                self.fluid.back_end[fluid] = None

            self.fluid.wrapper[fluid] = self.fluid.engine[fluid](fluid, back_end)

    def preprocess(self):
        self.num_eq = 0
        self.it = 0
        self.equations = {}

        for parameter in self.parameters:
            container = self.get_attr(parameter)
            if container.is_set and not container.solved:
                self.equations[self.num_eq] = parameter
                self.num_eq += self.parameters[parameter].num_eq
            elif container.solved:
                container.solved = False

        self.residual = np.zeros(self.num_eq)
        self.jacobian = OrderedDict()

    def simplify_specifications(self):
        systemvar_specs = []
        nonsystemvar_specs = []
        for name, container in self.property_data.items():
            if container.is_set:
                if name in ["m", "p", "h"]:
                    systemvar_specs += [name]
                elif name in ["T", "x", "Td_bp", "v"]:
                    nonsystemvar_specs += [name]

        specs = set(systemvar_specs + nonsystemvar_specs)
        num_specs = len(specs)

        if num_specs > 3:
            inputs = ", ".join(specs)
            msg = (
                "You have specified more than 3 parameters for the connection "
                f"{self.label} with a known fluid compoistion: {inputs}. This "
                "overdetermines the state of the fluid."
            )
            raise TESPyNetworkError(msg)

        if not self.h.is_set and self.p.is_set:
            if self.T.is_set:
                self.h.val_SI = h_mix_pT(self.p.val_SI, self.T.val_SI, self.fluid_data, self.mixing_rule, self.force_state)
                self.h.solved = True
                self.T.solved = True
            elif self.Td_bp.is_set:
                T_sat = T_sat_p(self.p.val_SI, self.fluid_data)
                self.h.val_SI = h_mix_pT(self.p.val_SI, T_sat + self.Td_bp.val, self.fluid_data, self.force_state)
                self.h.solved = True
                self.Td_bp.solved = True
            elif self.x.is_set:
                self.h.val_SI = h_mix_pQ(self.p.val_SI, self.x.val_SI, self.fluid_data)
                self.h.solved = True
                self.x.solved = True

        elif not self.h.is_set and not self.p.is_set:
            if self.T.is_set and self.x.is_set:
                self.p.val_SI = p_sat_T(self.T.val_SI, self.fluid_data)
                self.h.val_SI = h_mix_pQ(self.p.val_SI, self.x.val_SI, self.fluid_data)
                self.T.solved = True
                self.x.solved = True
                self.p.solved = True
                self.h.solved = True

    def get_parameters(self):
        return {
            'm': dc_prop(is_var=True, systemvariable=True),
            'p': dc_prop(is_var=True, systemvariable=True),
            'h': dc_prop(is_var=True, systemvariable=True),
            'vol': dc_prop(),
            's': dc_prop(),
            'fluid': dc_flu(),
            "T": dc_prop(func=self.T_func, deriv=self.T_deriv, num_eq=1),
            "v": dc_prop(func=self.v_func, deriv=self.v_deriv, num_eq=1),
            "x": dc_prop(func=self.x_func, deriv=self.x_deriv, num_eq=1),
            "Td_bp": dc_prop(
                func=self.Td_bp_func, deriv=self.Td_bp_deriv, num_eq=1
            ),
            "m_ref": dc_ref(
                func=self.primary_ref_func, deriv=self.primary_ref_deriv,
                num_eq=1, func_params={"variable": "m"}
            ),
            "p_ref": dc_ref(
                func=self.primary_ref_func, deriv=self.primary_ref_deriv,
                num_eq=1, func_params={"variable": "p"}
            ),
            "h_ref": dc_ref(
                func=self.primary_ref_func, deriv=self.primary_ref_deriv,
                num_eq=1, func_params={"variable": "h"}
            ),
            "T_ref": dc_ref(
                func=self.T_ref_func, deriv=self.T_ref_deriv, num_eq=1
            ),
            "v_ref": dc_ref(
                func=self.v_ref_func, deriv=self.v_ref_deriv, num_eq=1
            ),
        }

    def build_fluid_data(self):
        self.fluid_data = {
            fluid: {
                "wrapper": self.fluid.wrapper[fluid],
                "mass_fraction": self.fluid.val[fluid]
            } for fluid in self.fluid.val
        }

    def primary_ref_func(self, k, **kwargs):
        variable = kwargs['variable']
        self.get_attr(variable)
        ref = self.get_attr(f"{variable}_ref").ref
        self.residual[k] = (
            self.get_attr(variable).val_SI
            - ref.obj.get_attr(variable).val_SI * ref.factor + ref.delta_SI
        )

    def primary_ref_deriv(self, k, **kwargs):
        variable = kwargs['variable']
        ref = self.get_attr(f"{variable}_ref").ref
        if self.get_attr(variable).is_var:
            self.jacobian[k, self.get_attr(variable).J_col] = 1

        if ref.obj.get_attr(variable).is_var:
            self.jacobian[k, ref.obj.get_attr(variable).J_col] = -ref.factor

    def calc_T(self, T0=None):
        return T_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, T0=T0, force_state=self.force_state)

    def T_func(self, k, **kwargs):
        self.residual[k] = self.calc_T() - self.T.val_SI

    def T_deriv(self, k, **kwargs):
        if self.p.is_var:
            self.jacobian[k, self.p.J_col] = (
                dT_mix_dph(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, self.T.val_SI, force_state=self.force_state)
            )
        if self.h.is_var:
            self.jacobian[k, self.h.J_col] = (
                dT_mix_pdh(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, self.T.val_SI, force_state=self.force_state)
            )
        for fluid in self.fluid.is_var:
            # if not self._increment_filter[self.fluid.J_col[fluid]]:
            self.jacobian[k, self.fluid.J_col[fluid]] = dT_mix_ph_dfluid(
                self.p.val_SI, self.h.val_SI, fluid, self.fluid_data, self.mixing_rule, force_state=self.force_state
            )

    def T_ref_func(self, k, **kwargs):
        ref = self.T_ref.ref
        self.residual[k] = (
            self.calc_T() - ref.obj.calc_T() * ref.factor + ref.delta_SI
        )

    def T_ref_deriv(self, k, **kwargs):
        # first part of sum is identical to direct temperature specification
        self.T_deriv(k, **kwargs)
        ref = self.T_ref.ref
        if ref.obj.p.is_var:
            self.jacobian[k, ref.obj.p.J_col] = -(
                dT_mix_dph(ref.obj.p.val_SI, ref.obj.h.val_SI, ref.obj.fluid_data, ref.obj.mixing_rule)
            ) * ref.factor
        if ref.obj.h.is_var:
            self.jacobian[k, ref.obj.h.J_col] = -(
                dT_mix_pdh(ref.obj.p.val_SI, ref.obj.h.val_SI, ref.obj.fluid_data, ref.obj.mixing_rule)
            ) * ref.factor
        for fluid in ref.obj.fluid.is_var:
            if not self._increment_filter[ref.obj.fluid.J_col[fluid]]:
                self.jacobian[k, ref.obj.fluid.J_col[fluid]] = -dT_mix_ph_dfluid(
                    ref.obj.p.val_SI, ref.obj.h.val_SI, fluid, ref.obj.fluid_data, ref.obj.mixing_rule
                )

    def calc_viscosity(self, T0=None):
        try:
            return viscosity_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, T0=T0)
        except NotImplementedError:
            return np.nan


    def calc_vol(self, T0=None):
        try:
            return v_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, T0=T0, force_state=self.force_state)
        except NotImplementedError:
            return np.nan

    def v_func(self, k, **kwargs):
        self.residual[k] = self.calc_vol(T0=self.T.val_SI) * self.m.val_SI - self.v.val_SI

    def v_deriv(self, k, **kwargs):
        if self.m.is_var:
            self.jacobian[k, self.m.J_col] = self.calc_vol(T0=self.T.val_SI)
        if self.p.is_var:
            self.jacobian[k, self.p.J_col] = dv_mix_dph(self.p.val_SI, self.h.val_SI, self.fluid_data) * self.m.val_SI
        if self.h.is_var:
            self.jacobian[k, self.h.J_col] = dv_mix_pdh(self.p.val_SI, self.h.val_SI, self.fluid_data) * self.m.val_SI

    def v_ref_func(self, k, **kwargs):
        ref = self.v_ref.ref
        self.residual[k] = (
            self.calc_vol(T0=self.T.val_SI) * self.m.val_SI
            - ref.obj.calc_vol(T0=ref.obj.T.val_SI) * ref.obj.m.val_SI * ref.factor + ref.delta_SI
        )

    def v_ref_deriv(self, k, **kwargs):
        # first part of sum is identical to direct flow specification
        self.v_deriv(k, **kwargs)

        ref = self.v_ref.ref
        if ref.obj.m.is_var:
            self.jacobian[k, ref.obj.m.J_col] = -(
                ref.obj.calc_vol(T0=ref.obj.T.val_SI) * ref.factor
            )
        if ref.obj.p.is_var:
            self.jacobian[k, ref.obj.p.J_col] = -(
                dv_mix_dph(ref.obj.p.val_SI, ref.obj.h.val_SI, ref.obj.fluid_data)
                * ref.obj.m.val_SI * ref.factor
            )
        if ref.obj.h.is_var:
            self.jacobian[k, ref.obj.h.J_col] = -(
                dv_mix_pdh(ref.obj.p.val_SI, ref.obj.h.val_SI, ref.obj.fluid_data)
                * ref.obj.m.val_SI * ref.factor
            )

    def calc_x(self):
        try:
            return Q_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data)
        except NotImplementedError:
            return np.nan

    def x_func(self, k, **kwargs):
        # saturated steam fraction
        self.residual[k] = self.h.val_SI - h_mix_pQ(self.p.val_SI, self.x.val_SI, self.fluid_data)

    def x_deriv(self, k, **kwargs):
        if self.p.is_var:
            self.jacobian[k, self.p.J_col] = -dh_mix_dpQ(self.p.val_SI, self.x.val_SI, self.fluid_data)
        if self.h.is_var:
            self.jacobian[k, self.h.J_col] = 1

    def calc_T_sat(self):
        try:
            return T_sat_p(self.p.val_SI, self.fluid_data)
        except NotImplementedError:
            return np.nan

    def calc_Td_bp(self):
        try:
            return self.calc_T() - T_sat_p(self.p.val_SI, self.fluid_data)
        except NotImplementedError:
            return np.nan

    def Td_bp_func(self, k, **kwargs):
        # temperature difference to boiling point
        self.residual[k] = self.calc_Td_bp() - self.Td_bp.val_SI

    def Td_bp_deriv(self, k, **kwargs):
        if self.p.is_var:
            self.jacobian[k, self.p.J_col] = (
                dT_mix_dph(self.p.val_SI, self.h.val_SI, self.fluid_data)
                - dT_sat_dp(self.p.val_SI, self.fluid_data)
            )
        if self.h.is_var:
            self.jacobian[k, self.h.J_col] = dT_mix_pdh(
                self.p.val_SI, self.h.val_SI, self.fluid_data
            )

    def calc_s(self):
        return s_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data, self.mixing_rule, T0=self.T.val_SI, force_state=self.force_state)

    def calc_Q(self):
        return Q_mix_ph(self.p.val_SI, self.h.val_SI, self.fluid_data)

    def solve(self, increment_filter):
        self._increment_filter = increment_filter
        for k, parameter in self.equations.items():
            data = self.get_attr(parameter)
            data.func(k, **data.func_params)
            data.deriv(k, **data.func_params)

    def calc_results(self):
        self.T.val_SI = self.calc_T()
        number_fluids = get_number_of_fluids(self.fluid_data)
        _converged = True
        if number_fluids > 1:
            h_from_T = h_mix_pT(self.p.val_SI, self.T.val_SI, self.fluid_data, self.mixing_rule, force_state=self.force_state)
            if abs(h_from_T - self.h.val_SI) > ERR ** .5:
                self.T.val_SI = np.nan
                self.vol.val_SI = np.nan
                self.v.val_SI = np.nan
                self.s.val_SI = np.nan
                msg = (
                    "Could not find a feasible value for mixture temperature at "
                    f"connection {self.label}. The values for temperature, "
                    "specific volume, volumetric flow and entropy are set to nan."
                )
                logger.error(msg)
                _converged = False

        else:
            try:
                if not self.x.is_set:
                    self.x.val_SI = self.calc_x()
            except ValueError:
                self.x.val_SI = np.nan
            try:
                if not self.Td_bp.is_set:
                    self.Td_bp.val_SI = self.calc_Td_bp()
            except ValueError:
                self.x.val_SI = np.nan

        if _converged:
            self.vol.val_SI = self.calc_vol()
            self.v.val_SI = self.vol.val_SI * self.m.val_SI
            self.s.val_SI = self.calc_s()

        for prop in fpd.keys():
            self.get_attr(prop).val = convert_from_SI(
                prop, self.get_attr(prop).val_SI, self.get_attr(prop).unit
            )

        self.m.val0 = self.m.val
        self.p.val0 = self.p.val
        self.h.val0 = self.h.val
        self.fluid.val0 = self.fluid.val.copy()

    def check_pressure_bounds(self, fluid):
        if self.p.val_SI > self.fluid.wrapper[fluid]._p_max:
            self.p.val_SI = self.fluid.wrapper[fluid]._p_max
            logger.debug(self._property_range_message('p'))

        elif self.p.val_SI < self.fluid.wrapper[fluid]._p_min:
            try:
                # if this works, the temperature is higher than the minimum
                # temperature, we can access pressure values below minimum
                # pressure
                self.fluid.wrapper[fluid].T_ph(self.p.val_SI, self.h.val_SI)
            except ValueError:
                self.p.val_SI = self.fluid.wrapper[fluid]._p_min + 1e1
                logger.debug(self._property_range_message('p'))

    def check_enthalpy_bounds(self, fluid):
        # enthalpy
        try:
            hmin = self.fluid.wrapper[fluid].h_pT(
                self.p.val_SI, self.fluid.wrapper[fluid]._T_min + 1e-1,force_state=self.force_state
            )
        except ValueError:
            f = 1.05
            hmin = self.fluid.wrapper[fluid].h_pT(
                self.p.val_SI, self.fluid.wrapper[fluid]._T_min * f
            )
        if self.h.val_SI < hmin:
            if hmin < 0:
                self.h.val_SI = hmin * 0.9999
            else:
                self.h.val_SI = hmin * 1.0001
            logger.debug(self._property_range_message('h'))
        else:

            T = self.fluid.wrapper[fluid]._T_max
            while True:
                try:
                    hmax = self.fluid.wrapper[fluid].h_pT(self.p.val_SI, T, force_state=self.force_state)
                    break
                except ValueError as e:
                    T *= 0.99
                    if T < self.fluid.wrapper[fluid]._T_min:
                        raise ValueError(e) from e

            if self.h.val_SI > hmax:
                self.h.val_SI = hmax * 0.9999
                logger.debug(self._property_range_message('h'))

    def check_two_phase_bounds(self, fluid):

        if (self.Td_bp.val_SI > 0 or (self.state.val == 'g' and self.state.is_set)):
            h = self.fluid.wrapper[fluid].h_pQ(self.p.val_SI, 1)
            if self.h.val_SI < h:
                self.h.val_SI = h * 1.01
                logger.debug(self._property_range_message('h'))
        elif (self.Td_bp.val_SI < 0 or (self.state.val == 'l' and self.state.is_set)):
            h = self.fluid.wrapper[fluid].h_pQ(self.p.val_SI, 0)
            if self.h.val_SI > h:
                self.h.val_SI = h * 0.99
                logger.debug(self._property_range_message('h'))

    def check_temperature_bounds(self):
        r"""
        Check if temperature is within user specified limits.

        Parameters
        ----------
        c : tespy.connections.connection.Connection
            Connection to check fluid properties.
        """
        Tminlist=[]
        Tmaxlist=[]
        for f, w in self.fluid.wrapper.items():
            if self.fluid.val[f] > ERR and self.fluid.val[f] < 1-ERR:
                if self.force_state == 'l':
                    Tminlist.append(w._T_min)
                    if not w.back_end == 'INCOMP':
                        Tmaxlist.append(w.T_sat(self.p.val_SI))
                    else:
                        Tmaxlist.append(w._T_max)
                elif self.force_state == 'g':
                    Tmaxlist.append(w._T_max)
                    if not w.back_end == 'INCOMP':
                        Tminlist.append(w.T_sat(self.p.val_SI))
                    else:
                        Tminlist.append(w._T_min)
                else:
                    Tminlist.append(w._T_min)
                    Tmaxlist.append(w._T_max)            

        Tmin = max(Tminlist) * (1+ERR)
        Tmax = min(Tmaxlist) * (1-ERR)
        hmin = h_mix_pT(self.p.val_SI, Tmin, self.fluid_data, self.mixing_rule, force_state=self.force_state)
        hmax = h_mix_pT(self.p.val_SI, Tmax, self.fluid_data, self.mixing_rule, force_state=self.force_state)

        if self.h.val_SI < hmin:
            self.h.val_SI = hmin
            logger.debug(self._property_range_message('h'))

        if self.h.val_SI > hmax:
            self.h.val_SI = hmax
            logger.debug(self._property_range_message('h'))

    def _property_range_message(self, prop):
        r"""
        Return debugging message for fluid property range adjustments.

        Parameters
        ----------
        c : tespy.connections.connection.Connection
            Connection to check fluid properties.

        prop : str
            Fluid property.

        Returns
        -------
        msg : str
            Debugging message.
        """
        msg = (
            f"{fpd[prop]['text'][0].upper()}{fpd[prop]['text'][1:]} out of "
            f"fluid property range at connection {self.label}, adjusting value "
            f"to {self.get_attr(prop).val_SI} {fpd[prop]['SI_unit']}."
        )
        return msg

    def get_physical_exergy(self, pamb, Tamb):
        r"""
        Get the value of a connection's specific physical exergy.

        Parameters
        ----------
        p0 : float
            Ambient pressure p0 / Pa.

        T0 : float
            Ambient temperature T0 / K.

        Note
        ----
            .. math::

                e^\mathrm{PH} = e^\mathrm{T} + e^\mathrm{M}\\
                E^\mathrm{T} = \dot{m} \cdot e^\mathrm{T}\\
                E^\mathrm{M} = \dot{m} \cdot e^\mathrm{M}\\
                E^\mathrm{PH} = \dot{m} \cdot e^\mathrm{PH}
        """
        self.ex_therm, self.ex_mech = fp.functions.calc_physical_exergy(
            self.h.val_SI, self.s.val_SI, self.p.val_SI, pamb, Tamb,
            self.fluid_data, self.mixing_rule, self.T.val_SI
        )
        self.Ex_therm = self.ex_therm * self.m.val_SI
        self.Ex_mech = self.ex_mech * self.m.val_SI

        self.ex_physical = self.ex_therm + self.ex_mech
        self.Ex_physical = self.m.val_SI * self.ex_physical

    def get_chemical_exergy(self, pamb, Tamb, Chem_Ex):
        r"""
        Get the value of a connection's specific chemical exergy.

        Parameters
        ----------
        p0 : float
            Ambient pressure p0 / Pa.

        T0 : float
            Ambient temperature T0 / K.

        Chem_Ex : dict
            Lookup table for standard specific chemical exergy.

        Note
        ----
            .. math::

                E^\mathrm{CH} = \dot{m} \cdot e^\mathrm{CH}
        """
        if Chem_Ex is None:
            self.ex_chemical = 0
        else:
            self.ex_chemical = fp.functions.calc_chemical_exergy(
                pamb, Tamb, self.fluid_data, Chem_Ex, self.mixing_rule,
                self.T.val_SI
            )

        self.Ex_chemical = self.m.val_SI * self.ex_chemical


class Ref:
    r"""
    A reference object is used to reference (unknown) properties of connections
    to other connections.

    For example, reference the mass flow of one connection :math:`\dot{m}` to
    another mass flow :math:`\dot{m}_{ref}`:

    .. math::

        \dot{m} = \dot{m}_\mathrm{ref} \cdot \mathrm{factor} + \mathrm{delta}

    Parameters
    ----------
    obj : tespy.connections.connection.Connection
        Connection to be referenced.

    factor : float
        Factor to multiply specified property with.

    delta : float
        Delta to add after multiplication.
    """

    def __init__(self, ref_obj, factor, delta):

        if not isinstance(ref_obj, Connection):
            msg = 'First parameter must be object of type connection.'
            logger.error(msg)
            raise TypeError(msg)

        if not (isinstance(factor, int) or isinstance(factor, float)):
            msg = 'Second parameter must be of type int or float.'
            logger.error(msg)
            raise TypeError(msg)

        if not (isinstance(delta, int) or isinstance(delta, float)):
            msg = 'Thrid parameter must be of type int or float.'
            logger.error(msg)
            raise TypeError(msg)

        self.obj = ref_obj
        self.factor = factor
        self.delta = delta
        self.delta_SI = None

        msg = (
            f"Created reference object with factor {self.factor} and delta "
            f"{self.delta} referring to connection {ref_obj.label}"
        )
        logger.debug(msg)

    def get_attr(self, key):
        r"""
        Get the value of a reference attribute.

        Parameters
        ----------
        key : str
            The attribute you want to retrieve.

        Returns
        -------
        out :
            Specified attribute.
        """
        if key in self.__dict__:
            return self.__dict__[key]
        else:
            msg = 'Reference has no attribute \"' + key + '\".'
            logger.error(msg)
            raise KeyError(msg)
