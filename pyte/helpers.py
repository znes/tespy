"""
.. module:: helpers
    :platforms: all
    :synopsis: helpers for frequently used functionalities

.. moduleauthor:: Francesco Witte <francesco.witte@hs-flensburg.de>
"""

import CoolProp.CoolProp as CP
from CoolProp.CoolProp import PropsSI as CPPSI

import math
import numpy as np
import pandas as pd
import sys

from scipy.optimize import fsolve

global err
err = 1e-6
global molar_masses
molar_masses = {}

class MyNetworkError(Exception):
    pass


class MyConnectionError(Exception):
    pass


class MyComponentError(Exception):
    pass


def query_yes_no(question, default='yes'):
    """
    in prompt query

    :param question: question to ask in prompt
    :type question: str
    :param default: default answer
    :type default: str
    :returns: bool
    """
    valid = {'yes': True,
             'y': True,
             'ye': True,
             'no': False,
             'n': False}
    if default is None:
        prompt = '[y / n]'
    elif default == 'yes':
        prompt = '[Y / n]'
    elif default == 'no':
        prompt = '[y / N]'

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write('Please respond with \'yes\' or \'no\' '
                             '(or \'y\' or \'n\').\n')


def newton(func, deriv, flow, k):
    """
    find zero crossings of function func with 1-D newton algorithm,
    required for reverse functions of fluid mixtures

    :param func: function to find zero crossing in
    :type func: function
    :param deriv: derivative of the function
    :type deriv: function
    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param k: target value for function func
    :type k: numeric
    :returns: val (float) - val, so that func(flow, val) = k
    """
    res = 1
    val = 300
    i = 0
    while abs(res) >= err:
        res = k - func(flow, val)
        val += res / deriv(flow, val)

        if val < 69:
            val = 69
        i += 1

        if i > 10:
            print(flow)
            raise ValueError('No value found.')

    return val


def T_mix_ph(flow):
    """
    calculates the temperature from pressure and enthalpy,
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: T (float) - temperature in K
    """
    if num_fluids(flow[3]) > 1:
        return newton(h_mix_pT, dh_mix_pdT, flow, flow[2])
    else:
        for fluid, x in flow[3].items():
            if x > err:
                return CPPSI('T', 'H', flow[2], 'P', flow[1], fluid)


def T_mix_ps(flow, s):
    """
    calculates the temperature from pressure and entropy,
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param s: entropy in J / (kg * K)
    :type s: numeric
    :returns: T (float) - temperature in K
    """
    if num_fluids(flow[3]) > 1:
        return newton(s_mix_pT, ds_mix_pdT, flow, s)
    else:
        for fluid, x in flow[3].items():
            if x > err:
                return CPPSI('T', 'S', s, 'P', flow[1], fluid)


def dT_mix_dph(flow):
    """
    calculates partial derivate of temperature to pressure at
    constant enthalpy and fluid composition

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: dT / dp (float) - derivative in K / Pa
    """
    d = 1e-5
    u = flow.copy()
    l = flow.copy()
    u[1] += d
    l[1] -= d
    return (T_mix_ph(u) - T_mix_ph(l)) / (2 * d)


def dT_mix_pdh(flow):
    """
    method to calculate partial derivate of temperature to enthalpy at
    constant pressure and fluid composition

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: dT / dh (float) - derivative in (K * kg) / J
    """
    d = 1
    u = flow.copy()
    l = flow.copy()
    u[2] += d
    l[2] -= d
    return (T_mix_ph(u) - T_mix_ph(l)) / (2 * d)


def dT_mix_ph_dfluid(flow):
    """
    calculates partial derivates of temperature to fluid composition at
    constant pressure and enthalpy

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: dT / dfluid (np.array of floats) - derivatives in K
    """
    d = 1e-5
    u = flow.copy()
    l = flow.copy()
    vec_deriv = []
    for fluid, x in flow[3].items():
        if x > 1e-5:
            u[3][fluid] += d
            l[3][fluid] -= d
            vec_deriv += [(T_mix_ph(u) - T_mix_ph(l)) / (2 * d)]
            u[3][fluid] -= d
            l[3][fluid] += d
        else:
            vec_deriv += [0]

    return np.asarray(vec_deriv)


def h_mix_pT(flow, T):
    """
    calculates enthalpy from pressure and temperature

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param T: temperature in K
    :type T: numeric
    :returns: h (float) - enthalpy in J / kg
    """

    n = molar_massflow(flow[3])

    h = 0
    for fluid, x in flow[3].items():
        if x > err:
            ni = x / molar_masses[fluid]
            h += CPPSI('H', 'P', flow[1] * ni / n, 'T', T, fluid) * x

    return h


def dh_mix_pdT(flow, T):
    """
    calculates partial derivate of enthalpy to temperature at constant pressure

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param T: temperature in K
    :type T: numeric
    :returns: dh / dT (float) - derivative in J / (kg * K)
    """
    n = molar_massflow(flow[3])
    d = 2
    h_u = 0
    h_l = 0
    for fluid, x in flow[3].items():
        if x > err:
            pp = flow[1] * x / (molar_masses[fluid] * n)
            h_u += CPPSI('H', 'P', pp, 'T', T + d, fluid) * x
            h_l += CPPSI('H', 'P', pp, 'T', T - d, fluid) * x

    return (h_u - h_l) / (2 * d)


def h_mix_pQ(flow, Q):
    """
    calculates enthalpy from pressure and quality

    .. note::

       This function works for pure fluids only!

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param Q: fraction of vapour mass to total mass in 1
    :type Q: numeric
    :returns: h (float) - enthalpy in J / kg
    """
    n = molar_massflow(flow[3])

    h = 0
    for fluid, x in flow[3].items():
        if x > err:
            pp = flow[1] * x / (molar_masses[fluid] * n)
            pcrit = CPPSI('Pcrit', fluid)
            while pp > pcrit:
                flow[1] = flow[1] * 0.95

            h += CPPSI('H', 'P', pp, 'Q', Q, fluid) * x

    return h


def dh_mix_dpQ(flow, Q):
    """
    calculates partial derivative of enthalpy to pressure at constant quality

    .. note::

       This function works for pure fluids only!

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param Q: fraction of vapour mass to total mass in 1
    :type Q: numeric
    :returns: dh / dp (float) - derivative in J / (kg * Pa)
    """
    d = 1e-5
    u = flow.copy()
    l = flow.copy()
    u[1] += d
    l[1] -= d
    return (h_mix_pQ(u, Q) - h_mix_pQ(l, Q)) / (2 * d)


def v_mix_ph(flow):
    """
    calculates specific volume from pressure and enthalpy
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: v (float) - specific volume in kg / m :sup:`3`
    """
    if num_fluids(flow[3]) > 1:
        return v_mix_pT(flow, T_mix_ph(flow))
    else:
        for fluid, x in flow[3].items():
            if x > err:
                return 1 / CPPSI('D', 'P', flow[1], 'H', flow[2], fluid)


def v_mix_pT(flow, T):
    """
    calculates specific volume from pressure and temperature
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param T: temperature in K
    :type T: numeric
    :returns: v (float) - specific volume in kg / m :sup:`3`
    """
    n = molar_massflow(flow[3])

    d = 0
    for fluid, x in flow[3].items():
        if x > err:
            pp = flow[1] * x / (molar_masses[fluid] * n)
            d += CPPSI('D', 'P', pp, 'T', T, fluid) * x

    return 1 / d


def s_mix_ph(flow):
    """
    calculates entropy from pressure and enthalpy
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: s (float) - entropy in J / (kg * K)
    """
    if num_fluids(flow[3]) > 1:
        return s_mix_pT(flow, T_mix_ph(flow))
    else:
        for fluid, x in flow[3].items():
            if x > err:
                return CPPSI('S', 'P', flow[1], 'H', flow[2], fluid)


def s_mix_pT(flow, T):
    """
    calculates entropy from pressure and temperature
    uses CoolProp reverse functions for pure fluids, newton for mixtures

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param T: temperature in K
    :type T: numeric
    :returns: s (float) - entropy in J / (kg * K)
    """
    n = molar_massflow(flow[3])

    s = 0
    for fluid, x in flow[3].items():
        if x > err:
            pp = flow[1] * x / (molar_masses[fluid] * n)
            s += CPPSI('S', 'P', pp, 'T', T, fluid) * x

    return s


def ds_mix_pdT(flow, T):
    """
    calculates partial derivate of entropy to temperature at constant pressure

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :param T: temperature in K
    :type T: numeric
    :returns: ds / dT (float) - derivative in J / (kg * K :sup:`2`)
    """
    n = molar_massflow(flow[3])
    d = 2
    s_u = 0
    s_l = 0
    for fluid, x in flow[3].items():
        if x > err:
            pp = flow[1] * x / (molar_masses[fluid] * n)
            s_u += CPPSI('S', 'P', pp, 'T', T + d, fluid) * x
            s_l += CPPSI('S', 'P', pp, 'T', T - d, fluid) * x

    return (s_u - s_l) / (2 * d)


def molar_massflow(flow):
    """
    calculates molar massflow

    :param flow: vector containing [mass flow, pressure, enthalpy, fluid]
    :type flow: list
    :returns: mm (float) - molar massflow in mol / s
    """
    mm = 0
    for fluid, x in flow.items():
        if x > err:
            try:
                mm += x / molar_masses[fluid]
            except:
                mm += x / CPPSI('molar_mass', fluid)

    return mm


def num_fluids(fluids):
    """
    calculates number of fluids in fluid vector

    :param fluids: fluid vector {fluid: mass fraction}
    :type fluids: dict
    :returns: n (int) - number of fluids in fluid vector in 1
    """
    n = 0
    for fluid, x in fluids.items():
        if x > err:
            n += 1

    return n


def fluid_structure(fluid):
    """
    gets the chemical formular of a fluid

    :param fluid: alias of the fluid
    :type fluid: str
    :returns: parts (dict) - returns the elements of the fluid {element: n}
    """
    parts = {}
    for element in CP.get_fluid_param_string(fluid, 'formula').split('}'):
        if element != '':
            el = element.split('_{')
            parts[el[0]] = int(el[1])

    return parts

def lamb(re, ks, d):
    """
    calculates darcy friction factor

    :param re: reynolds number in 1
    :type re: numeric
    :param ks: roughness in m
    :type ks: numeric
    :param d: pipe diameter in m
    :type d: numeric
    :returns: lambda (float) - darcy friction factor in 1
    """
    if re <= 2320:
        return 64 / re
    else:
        if re * ks / d < 65:
            if re <= 1e5:
                return 0.3164 * re ** (-0.25)
            elif re > 1e5 and re < 5e6:
                return 0.0032 + 0.221 * re ** (-0.237)
            else:
                l0 = 0.0001
                func = lambda l: (2 * math.log(re * math.sqrt(l)) - 0.8 - 1 /
                                  math.sqrt(l))
                return fsolve(func, l0)
        elif re * ks / d > 1300:
            return 1 / (2 * math.log(3.71 * d / ks)) ** 2
        else:
            l0 = 0.002
            func = lambda l: (2 * math.log(2.51 / (re * math.sqrt(l)) +
                              ks / d * 0.269) + 1 / math.sqrt(l))
            return fsolve(func, l0)
