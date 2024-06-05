## test docker image

docker build -t shptozarr_res .
docker run -it shptozarr_res python shp_to_zarr.py https://s3.waw3-1.cloudferro.com/emodnet/emodnet_native/emodnet_seabed_habitats/essential_ocean_variables/biogenic_substrate_in_europe/BiogenicSubstrate_2023.zip 0.01

or 

docker run samfooks/shptozarr:latest python shp_to_zarr.py https://s3.waw3-1.cloudferro.com/emodnet/emodnet_native/archive/human_activities_windfarms/EMODnet_HA_Energy_WindFarms_polygons_20231124.zip 0.01   

