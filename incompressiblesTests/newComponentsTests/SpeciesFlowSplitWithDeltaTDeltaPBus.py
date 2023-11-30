import logging

from tespy.components import SimpleHeatExchanger, Source, Sink, Merge, Separator 
from tespy.tools import ComponentProperties
from tespy.connections import Connection, Bus
from tespy.networks import Network
import numpy as np

from tespy.tools.data_containers import ComponentProperties as dc_cp
from tespy.tools.data_containers import GroupedComponentProperties as dc_gcp

from tespy.components.newComponents import \
    DiabaticSimpleHeatExchanger,MergeDeltaP,SeparatorWithSpeciesSplits, \
        SeparatorWithSpeciesSplitsDeltaT, SeparatorWithSpeciesSplitsDeltaTDeltaP, SeparatorWithSpeciesSplitsDeltaTDeltaPBus,SimpleHeatExchangerDeltaP

logging.basicConfig(level=logging.DEBUG)

# %%

# caution, must write "Water" (capital W) in INCOMP backend -> CoolProp bug? Intentional?
fluids = ["INCOMP::Water", "INCOMP::T66"]
nw = Network(fluids=fluids, m_unit='kg / s', p_unit='bar', T_unit='C',h_unit='kJ / kg', h_range=[-1e2,4e3], iterinfo=True)

so = Source("Source")
se = SeparatorWithSpeciesSplitsDeltaTDeltaPBus("Separator",num_out=2)
si1 = Sink("Sink 1")
hx = SimpleHeatExchangerDeltaP("HX")
si2 = Sink("Sink 2")


c1 = Connection(so, "out1", se, "in1", label="1")
c2 = Connection(se, "out1", si1, "in1", label="2")
c3 = Connection(se, "out2", hx, "in1", label="3")
c4 = Connection(hx, "out1", si2, "in1", label="4")

nw.add_conns(c1, c2, c3, c4)

# set global guess values 
m0 = 1    # transform unit at some point [this is kt/yr]
h0 = 1e2        # global guess value in kJ/kg
p0 = 5        # global guess value in bar

for c in nw.conns['object']:
    n_fl = 2 # len(nw.fluids)
    c.set_attr(m0=m0,h0=h0,p0=p0,fluid0={'INCOMP::Water': 1/n_fl, 'INCOMP::T66': 1/n_fl})

# set some generic data for starting values
c1.set_attr(m=1, p=5, h=h0, fluid={"INCOMP::Water": 0.9, "INCOMP::T66": 0.1}, mixing_rule="incompressible")
c2.set_attr(fluid={"INCOMP::Water": 0.8, "INCOMP::T66": 0.2})

se.set_attr(SFS={
    'val': 0.6, 'is_set': True, 
    'split_fluid' : 'INCOMP::T66', 'split_outlet' : "out1"})

# Now it is possible to set the temperatures out of the separator differently
c2.set_attr(T=20,p=5)
c3.set_attr(T=10,p=5)

#c4.set_attr(p=1)
hx.set_attr(deltaP=1)


heat_bus = Bus('total heat input', P=0)
heat_bus.add_comps({'comp': se, 'char': 1}, {'comp': hx, 'char': 1})
nw.add_busses(heat_bus)

nw.solve("design")
if not nw.converged:
    raise Exception("not converged")
nw.print_results()
print(nw.results['Connection'])
m_T66_c1 = c1.m.val * c1.fluid.val['T66']
m_T66_c2 = c2.m.val * c2.fluid.val['T66']
print(f"\n Species flow split is {m_T66_c2/m_T66_c1}")
print(f"\n")



