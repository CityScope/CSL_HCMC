
import sys
sys.path.insert(0,'./CS_Spatial_Modules')
# import os
# os.chdir('CS_Spatial_Modules')
import CS_Indicators as CS
import geogrid_tools
from brix import Indicator, Handler
import geopandas as gpd
import pandas as pd
# os.chdir('../')
import urllib
import json


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

simpop_df_sample=simpop_df.sample(frac=0.1)

# Set up the Table

table_name='hcmc_rd'
types=json.load(open('../Data/Table/types.json'))
properties=geogrid_tools.init_geogrid(table_name, types=types, interactive_zone=None)

get_url='https://cityio.media.mit.edu/api/table/'+table_name+'/'
with urllib.request.urlopen(get_url+'/GEOGRID/') as url:
    geogrid=gpd.read_file(url.read().decode())

centroids=geogrid['geometry'].centroid
geogrid['x_centroid']=[c.x for c in centroids]
geogrid['y_centroid']=[c.y for c in centroids]
geogrid

H=Handler(table_name=table_name)
H.reset_geogrid_data()

# Custom inputs to Modules
score_dict={'walkable_housing': {'col':'res_total', 'from': 'source_emp'},
                            'walkable_employment': {'col':'emp_total', 'from': 'source_res'},
                            'walkable_healthcare': {'col':'emp_naics_62', 'from': 'source_res'},
                            'walkable_hospitality': {'col':'emp_naics_72', 'from': 'source_res'}}

profile_descriptions = [{"name": '1',
                                'color': "#7fc97f"},
                                 {"name": '2',
                                'color': "#beaed4"},
                                 {"name": '3',
                                'color': "#fdc086"},
                                {"name": '4',
                                'color': "#ffff99"},
                                ]

# Run modules
d=CS.Density_Indicator(zones=zones)
# p=CS.Proximity_Indicator(zones=zones, geogrid=geogrid, score_dict=score_dict)
m=CS.Mobility_indicator(zones, geogrid, table_name, simpop_df, 
                     profile_descriptions=profile_descriptions, simpop_sample_frac=0.005)
p=CS.Proximity_Indicator(zones=zones, geogrid=geogrid, score_dict=score_dict)
H.add_indicators([
    d,
    p, 
    m
])

H.listen()
