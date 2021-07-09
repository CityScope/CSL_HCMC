
import sys
sys.path.insert(0,'./CS_Spatial_Modules')
import CS_Indicators as CS
import PreCompOsmNet
import Simulation
import geogrid_tools
from brix import Indicator, Handler
import geopandas as gpd
import pandas as pd
import urllib
import json
import pickle
import json
import numpy as np

# Load the City Data

zones=gpd.read_file('../outputs/zones.geojson').set_index('GEOID').fillna(0)
sim_zones=set(zones.loc[zones['sim_area']].index)
all_zones=set(zones.index)
simpop_df=pd.read_csv('../outputs/simpop.csv')
simpop_df['home_geoid']=simpop_df['home_geoid'].astype(str)
simpop_df['work_geoid']=simpop_df['work_geoid'].astype(str)
simpop_df['earnings']=simpop_df['earnings'].astype(str)
simpop_df=simpop_df.loc[((simpop_df['home_geoid'].isin(all_zones))&
                         (simpop_df['work_geoid'].isin(all_zones)))]


### Only include people who:
# both live AND work in the MODEL area
# either live OR work in the SIMULATION area
simpop_df=simpop_df.loc[((simpop_df['home_geoid'].isin(all_zones))&
                         (simpop_df['work_geoid'].isin(all_zones)))]
simpop_df=simpop_df.loc[((simpop_df['home_geoid'].isin(sim_zones))|
                         (simpop_df['work_geoid'].isin(sim_zones)))]
frac=0.5
simpop_df_sample=simpop_df.sample(frac=frac)
total_sampling_factor=frac*0.01 # survey itself was already a 1% sample

# Set up the Table

table_name='hcmc_rd'
types=json.load(open('../Data/Table/types.json'))

get_url='https://cityio.media.mit.edu/api/table/'+table_name+'/'
with urllib.request.urlopen(get_url+'/GEOGRID/') as url:
    geogrid=gpd.read_file(url.read().decode())

centroids=geogrid['geometry'].centroid
geogrid['x_centroid']=[c.x for c in centroids]
geogrid['y_centroid']=[c.y for c in centroids]
geogrid

H=Handler(table_name=table_name)
H.reset_geogrid_data()

# Mobility system and Mode Choice Model
external_hw_tags=["motorway","motorway_link",
                  "trunk","trunk_link",
                  "primary", "primary_link"
                 ]

networks, mode_dicts, route_lengths=PreCompOsmNet.create_2_scale_osmnx_network(
    zones.loc[zones['sim_area']], zones.loc[zones['model_area']],
    add_modes=[{'name': 'walk', 'speed': 4800/3600},
               {'name': 'cycle', 'speed': 14000/3600},
               {'name': 'pt', 'speed': 25000/3600}],
    external_hw_tags=external_hw_tags)


mode_dicts={}
mode_dicts['Motorcycle']={'target_network_id': 'drive','travel_time_metric': 'travel_time_drive'}
mode_dicts['Bicycle']={'target_network_id': 'drive','travel_time_metric': 'travel_time_cycle'}
mode_dicts['Electric bicycle']={'target_network_id': 'drive','travel_time_metric': 'travel_time_cycle'}
mode_dicts['Walking']={'target_network_id': 'drive','travel_time_metric': 'travel_time_walk'}
mode_dicts['Bus']={'target_network_id': 'drive','travel_time_metric': 'travel_time_pt'}
mode_dicts['Car']={'target_network_id': 'drive','travel_time_metric': 'travel_time_drive'}
mode_dicts['Others']={'target_network_id': 'drive','travel_time_metric': 'travel_time_drive'}

modes={mode: Simulation.Mode(mode_dicts[mode]) for mode in mode_dicts}
mob_sys=Simulation.MobilitySystem(modes=modes, networks=networks)


mc_model=pickle.load(open('../outputs/mode_choice_model.p', 'rb'))
model_description=json.load(open('../outputs/mc_model_features.json'))

class Logistic_Mode_Choice_model():
    def __init__(self, mc_model, model_description):
        self.options=model_description['mode_order']
        self.features=model_description['features']
        self.dummy_map=model_description['dummy_map']
        self.model=mc_model
    
    def predict_modes(self, all_trips_df):
        data=all_trips_df.copy()
        for attr in self.dummy_map:
            dummys=pd.get_dummies(data[attr], prefix=self.dummy_map[attr])
            for col in dummys.columns:
                data[col]=dummys[col]
        for feat in self.features:
            if not feat in data.columns:
                print('{} not in data'.format(feat))
                data[feat]=0
        X=data[self.features]
        y_pred_proba=self.model.predict_proba(X)
        # Do all probabilistic samples with single call random number generator
        y_pred_proba_cum=np.cumsum(y_pred_proba, axis=1)
        p_cut=np.random.uniform(0, 1, len(data))
        y_pred=[self.options[np.argmax(y_pred_proba_cum[i]>p_cut[i])] for i in range(len(data))]
#         y_pred=[self.options[np.random.choice(range(len(y_pred_proba[i])), size=1, replace=True, p=y_pred_proba[i]
#                                 )[0]] for i in range(len(y_pred_proba))]
        all_trips_df['mode']=y_pred
        return all_trips_df

mode_colors=['#7fc97f',
'#beaed4',
'#fdc086',
'#ffff99',
'#386cb0',
'#f0027f',
'#bf5b17']

mode_descriptions=[{'name': model_description['mode_order'][i], 'color': mode_colors[i]
                  } for i in range(len(model_description['mode_order']))]

profile_descriptions = [{"name": '1',
                        'color': "#7fc97f"},
                         {"name": '2',
                        'color': "#beaed4"},
                         {"name": '3',
                        'color': "#fdc086"},
                        {"name": '4',
                        'color': "#ffff99"},
                        ]


# Custom inputs to Modules
score_dict={'walkable_housing': {'col':'res_total', 'from': 'source_emp'},
                            'walkable_employment': {'col':'emp_total', 'from': 'source_res'},
                            'walkable_healthcare': {'col':'emp_naics_62', 'from': 'source_res'},
                            'walkable_hospitality': {'col':'emp_naics_72', 'from': 'source_res'}}


# Run modules
d=CS.Density_Indicator(zones=zones)
m=CS.Mobility_indicator(zones, geogrid, table_name, simpop_df, mob_sys,
                        mode_choice_model=Logistic_Mode_Choice_model(mc_model, model_description),
                        mode_descriptions=mode_descriptions,
                        profile_descriptions=profile_descriptions,
                        route_lengths=route_lengths, simpop_sample_frac=total_sampling_factor)
p=CS.Proximity_Indicator(zones=zones, geogrid=geogrid, score_dict=score_dict)
H.add_indicators([
    d,
    p, 
    m
])

H.listen()
