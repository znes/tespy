# %%
import logging


from tespy.components import HeatExchangerSimple, Source, Sink, Merge
from tespy.connections import Connection
from tespy.networks import Network
import numpy as np

from tespy.tools.data_containers import ComponentProperties as dc_cp
from tespy.tools.data_containers import GroupedComponentProperties as dc_gcp

from tespy.components.newcomponents import DiabaticSimpleHeatExchanger,MergeWithPressureLoss,SeparatorWithSpeciesSplits



# %%

# caution, must write "Water" (capital W) in INCOMP backend -> CoolProp bug? Intentional?
fluids = ["INCOMP::FoodWater", "INCOMP::FoodProtein"]


nw = Network(fluids=fluids, p_unit="bar", T_unit="C")

so = Source("Source")
so2 = Source("Source2")

me = MergeWithPressureLoss("Merge")
si = Sink("Sink")

c1 = Connection(so, "out1", me, "in1", label="2")
c3 = Connection(so2, "out1", me, "in2", label="3")
c4 = Connection(me, "out1", si, "in1", label="4")

nw.add_conns(c1, c3, c4)

# set some generic data for starting values
c1.set_attr(m=1, p=2.1, h=0.5e5, fluid={"FoodWater": 0.9, "FoodProtein": 0.1})
# mix with pure water
c3.set_attr(m=0.05, p=2.2, h=0.5e5, fluid={"FoodWater": 1, "FoodProtein": 0})

# set pressure ratios of heater and merge
me.set_attr(deltaP=1)
#c4.set_attr(p=1)

nw.solve("design")

nw.print_results()
print(nw.results['Connection'])
