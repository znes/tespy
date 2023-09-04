
import CoolProp as CP
from CoolProp.CoolProp import AbstractState


class FluidPropertyWrapper:

    def _not_implemented(self) -> None:
        raise NotImplementedError(
            f"Method is not implemented for {self.__class__.__name__}."
        )

    def _is_below_T_critical(self, T):
        self._not_implemented()

    def _make_p_subcritical(self, p):
        self._not_implemented()

    def T_ph(self, p, h):
        self._not_implemented()

    def T_ps(self, p, s):
        self._not_implemented()

    def h_pT(self, p, T):
        self._not_implemented()

    def h_QT(self, Q, T):
        self._not_implemented()

    def s_QT(self, Q, T):
        self._not_implemented()

    def T_sat(self, p):
        self._not_implemented()

    def p_sat(self, T):
        self._not_implemented()

    def Q_ph(self, p, h):
        self._not_implemented()

    def d_ph(self, p, h):
        self._not_implemented()

    def d_pT(self, p, T):
        self._not_implemented()

    def d_QT(self, Q, T):
        self._not_implemented()

    def viscosity_ph(self, p, h):
        self._not_implemented()

    def viscosity_pT(self, p, T):
        self._not_implemented()

    def s_ph(self, p, h):
        self._not_implemented()

    def s_pT(self, p, T):
        self._not_implemented()


class CoolPropWrapper(FluidPropertyWrapper):

    def __init__(self, fluid, back_end=None) -> None:
        self.fluid = fluid
        if back_end is None:
            self.back_end = "HEOS"
        else:
            self.back_end = back_end

        self.AS = AbstractState(self.back_end, fluid)
        self._set_constants()

    def _set_constants(self):
        self._T_min = self.AS.trivial_keyed_output(CP.iT_min)
        self._T_max = self.AS.trivial_keyed_output(CP.iT_max)

        if self.back_end == "INCOMP":
            self._p_min = 1e2
            self._p_max = 1e8
            self._p_crit = 1e2
            self._T_crit = None
            self._molar_mass = 1
        else:
            self._p_min = self.AS.trivial_keyed_output(CP.iP_min)
            self._p_max = self.AS.trivial_keyed_output(CP.iP_max)
            self._p_crit = self.AS.trivial_keyed_output(CP.iP_critical)
            self._T_crit = self.AS.trivial_keyed_output(CP.iT_critical)
            self._molar_mass = self.AS.trivial_keyed_output(CP.imolar_mass)

    def _is_below_T_critical(self, T):
        return T < self._T_crit

    def _make_p_subcritical(self, p):
        if p > self._p_crit:
            p = self._p_crit * 0.99
        return p

    def isentropic(self, p_1, h_1, p_2):
        return self.h_ps(p_2, self.s_ph(p_1, h_1))

    def T_ph(self, p, h):
        self.AS.update(CP.HmassP_INPUTS, h, p)
        return self.AS.T()

    def T_ps(self, p, s):
        self.AS.update(CP.PSmass_INPUTS, p, s)
        return self.AS.T()

    def h_pQ(self, p, Q):
        self.AS.update(CP.PQ_INPUTS, p, Q)
        return self.AS.hmass()

    def h_ps(self, p, s):
        self.AS.update(CP.PSmass_INPUTS, p, s)
        return self.AS.hmass()

    def h_pT(self, p, T):
        self.AS.update(CP.PT_INPUTS, p, T)
        return self.AS.hmass()

    def h_QT(self, Q, T):
        self.AS.update(CP.QT_INPUTS, Q, T)
        return self.AS.hmass()

    def s_QT(self, Q, T):
        self.AS.update(CP.QT_INPUTS, Q, T)
        return self.AS.smass()

    def T_sat(self, p):
        p = self._make_p_subcritical(p)
        self.AS.update(CP.PQ_INPUTS, p, 1)
        return self.AS.T()

    def p_sat(self, T):
        if T > self._T_crit:
            T = self._T_crit * 0.99

        self.AS.update(CP.QT_INPUTS, 1, T)
        return self.AS.p()

    def Q_ph(self, p, h):
        p = self._make_p_subcritical(p)
        self.AS.update(CP.HmassP_INPUTS, h, p)
        return self.AS.Q()

    def d_ph(self, p, h):
        self.AS.update(CP.HmassP_INPUTS, h, p)
        return self.AS.rhomass()

    def d_pT(self, p, T):
        self.AS.update(CP.PT_INPUTS, p, T)
        return self.AS.rhomass()

    def d_QT(self, Q, T):
        self.AS.update(CP.QT_INPUTS, Q, T)
        return self.AS.rhomass()

    def viscosity_ph(self, p, h):
        self.AS.update(CP.HmassP_INPUTS, h, p)
        return self.AS.viscosity()

    def viscosity_pT(self, p, T):
        self.AS.update(CP.PT_INPUTS, p, T)
        return self.AS.viscosity()

    def s_ph(self, p, h):
        self.AS.update(CP.HmassP_INPUTS, h, p)
        return self.AS.smass()

    def s_pT(self, p, T):
        self.AS.update(CP.PT_INPUTS, p, T)
        return self.AS.smass()


try:
    import pyromat as pm
    pm.config['unit_energy'] = "J"
    pm.config['unit_pressure'] = "Pa"
    pm.config['unit_molar'] = "mol"
except ModuleNotFoundError:
    pm = None


class PyromatIdealGasWrapper(FluidPropertyWrapper):

    def __init__(self, fluid, backend=None) -> None:
        if pm is None:
            msg = (
                "To use the pyromat fluid properties you need to install "
                "pyromat."
            )
            raise ModuleNotFoundError(msg)
        self.fluid = fluid

        self.AS = pm.get(f"ig.{fluid}")
        self._set_constants()

    def _set_constants(self):
        # self._p_crit = self.AS.trivial_keyed_output(CP.iP_critical)
        # self._T_crit = self.AS.trivial_keyed_output(CP.iT_critical)
        self._p_min, self._p_max = 100, 1000e5
        self._T_min, self._T_max = self.AS.Tlim()
        self._molar_mass = self.AS.mw()

    def T_ph(self, p, h):
        return self.AS.T(p=p, h=h)[0]

    def T_ps(self, p, s):
        return self.AS.T(p=p, s=s)[0]

    def h_pT(self, p, T):
        return self.AS.h(p=p, T=T)[0]

    def T_ph(self, p, h):
        return self.AS.T(p=p, h=h)[0]

    def T_ps(self, p, s):
        return self.AS.T(p=p, s=s)[0]

    def h_pT(self, p, T):
        return self.AS.h(p=p, T=T)[0]

    def d_ph(self, p, h):
        return self.AS.d(p=p, h=h)[0]

    def d_pT(self, p, T):
        return self.AS.d(p=p, T=T)[0]

    def s_ph(self, p, h):
        return self.AS.s(p=p, h=h)[0]

    def s_pT(self, p, T):
        return self.AS.s(p=p, T=T)[0]


class PyromatMulitphaseWrapper(PyromatIdealGasWrapper):

    def __init__(self, fluid, backend=None) -> None:
        if pm is None:
            msg = (
                "To use the pyromat fluid properties you need to install "
                "pyromat."
            )
            raise ModuleNotFoundError(msg)
        self.fluid = fluid

        self.AS = pm.get(f"mp.{fluid}")
        self._set_constants()

    def h_QT(self, Q, T):
        return self.AS.h(x=Q, T=T)[0]

    def s_QT(self, Q, T):
        return self.AS.s(x=Q, T=T)[0]

    def T_boiling(self, p):
        return self.AS.T(x=1, p=p)[0]

    def p_boiling(self, T):
        return self.AS.p(x=1, T=T)[0]

    def Q_ph(self, p, h):
        return self.AS.x(p=p, h=h)[0]

    def d_QT(self, Q, T):
        return self.AS.d(x=Q, T=T)[0]