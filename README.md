# edito-shp-to-zarr
Shapefile to zarr process for EDITO Process Catalog

This repository shows the components used to make the Shapefile to Zarr process available to convert Shapefiles directly to zarr in the EDITO Infra Process Catalog. It deploys a containerized application that converts Shapefiles to Zarr format. The application is built using Python and leverages libraries such as geopandas, zarr, dask, and numpy.

## Application 
The application (shp_to_zarr.py) takes a URL to a Shapefile as an argument. It downloads the file, opens it as a geopandas geodataframe, and renames 'lat' and 'lon' variables to 'latitude' and 'longitude' if they exist. The geodataframe is then chunked based on the latitude and longitude dimensions. The chunked geodataframe is converted to Zarr format and stored in the path specified by ARCO_ASSET_TEMP_DIR.

## Usage 
Here are the Helm charts and yaml files used to deploy this process on the EDITO Infra Process Catalog

## License: 
CC BY-4.0

