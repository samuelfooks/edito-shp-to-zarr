import geopandas as gpd
import xarray as xr
import numpy as np
import rasterio.features
import rasterio.transform
import os
import fiona
import pandas as pd
import stat
import os
import sys
import requests
from zipfile import ZipFile
from tempfile import TemporaryDirectory
# Suppress pandas SettingWithCopyWarning

pd.set_option('mode.chained_assignment', None)


# Function to download and extract the zip file
def download_and_extract_zip(zip_url):
    zip_file_path = '/zipfiles/temp.zip'
    # Download the zip file
    response = requests.get(zip_url)
    with open(zip_file_path, "wb") as f:
        f.write(response.content)
    # Extract the contents of the zip file
    with ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall('/zipfiles')
    # Find the .shp file
    shp_file_path = None
    for file in os.listdir('/zipfiles'):
        if file.endswith(".shp"):
            shp_file_path = os.path.join('/zipfiles', file)
            break
    return shp_file_path
    
    
def gdf2zarrconverter(shp_file_path, resolution=0.01):

    title = os.path.splitext(os.path.basename(shp_file_path))[0]
    def cleaner(data):
        if data == '0' or data == ' ' or data == np.nan or data == 'nan':
            data = 'None'
        return data


    def encode_categorical(data):
        # Convert the input data to a list to find unique values
        datalist = list(np.unique(data))
        
        # Iterate over each value in the array and replace ' ' with 'None'
        data[data == ' '] = 'None'
        data[data == '0'] = 'None'
        unique_categories = np.unique(data)
        
    # Create a mapping of categories to numeric values
        category_mapping = {'None': 1}  # 'None' is mapped to 1 initially
        
        # Assign numeric values to the rest of the categories
        counter = 2
        for category in unique_categories:
            if category != 'None':
                category_mapping[category] = counter
                counter += 1
        
        # Encode the data using the category mapping
        encoded_data = np.array([category_mapping.get(item, np.nan) for item in data])
        
        return encoded_data, category_mapping
    
    gdf = gpd.read_file(shp_file_path)


    # Find the latitude and longitude bounds
    lon_min, lat_min, lon_max, lat_max = gdf.total_bounds

    # Calculate width and height based on resolution in EPSG 4326 degrees
    resolution = 0.01 #about 10 km

    width = int(np.ceil((lon_max - lon_min) / resolution))
    height = int(np.ceil((lat_max - lat_min) / resolution))


    # Find categorical columns
    categorical_columns = gdf.select_dtypes(include=['object']).columns.tolist()
    numerical_columns = gdf.select_dtypes(include=[np.number]).columns.tolist()

    #clean categorical data
    for column in categorical_columns:
        gdf[column]= gdf[column].apply(lambda x: cleaner(x))
        gdf[column] = gdf[column].fillna('None')
    
    #clean numerical data  
    for column in numerical_columns:
        gdf[column] = gdf[column].fillna(0)

    # Encode categorical columns
    category_mappings = {}
    categorical_raster_layers = {}

    #encode the categorical columns, make a raster of 0s same shape as the height and width
    for column in categorical_columns:
        encoded_data, category_mapping = encode_categorical(gdf[column])
        gdf[column] = encoded_data
        category_mappings[column] = category_mapping
        categorical_raster_layers[column] = np.zeros((height, width), dtype=np.float32)
 
    # Create numerical data arrays
    numerical_data = {}
    for column in numerical_columns:
        numerical_data[column] = gdf[column].values
        #print(f'{column} values {np.unique(list(gdf[column].values.astype(np.float64)))}')

    # Create an empty raster image with the desired dimensions
    raster_transform = rasterio.transform.from_bounds(lon_min, lat_min, lon_max, lat_max, width, height)

    # Rasterize the categorical columns into the empty images
    for column in categorical_columns:
        categories = gdf[column].to_numpy()
        #print(categories.max().item())
        raster = categorical_raster_layers[column]
        categorical_raster_layers[column] = rasterio.features.rasterize(
            ((geom, value) for geom, value in zip(gdf.geometry, categories)),
            out=raster,
            transform=raster_transform,
            merge_alg=rasterio.enums.MergeAlg.replace,
            dtype=np.float32,
        )
        #print(column + ' ' + str(categorical_raster_layers[column].max().item()))
        
    #Create numerical raster layers
    numerical_raster_layers = {}
    for column, data in numerical_data.items():
        raster = np.zeros((height, width), dtype=np.float32)
        rasterio.features.rasterize(
            [(geom, val) for geom, val in zip(gdf.geometry, data)],
            out=raster,
            transform=raster_transform,
            dtype=np.float32,
        )
        
        numerical_raster_layers[column] = raster
        print (f'{column} rasterized')
        

    # Create an Xarray Dataset to include the raster layers and the category mappings as separate variables
    dataset = xr.Dataset(coords={'latitude':  np.round(np.linspace(lat_min, lat_max, height, dtype=float), decimals=4),
                            'longitude': np.round(np.linspace(lon_min, lon_max, width, dtype=float), decimals=4)})

    #set latitude coordinates in increasing order
    dataset = dataset.reindex(latitude=dataset.latitude[::-1])

    #add latitude and longitude to the categorical layers
    for column, raster in categorical_raster_layers.items():
        dataset[column] = (['latitude', 'longitude'], raster)
        
        #set encodings in the attributes of the dataset variable(column from geodataframe)
        dataset[column].attrs = category_mappings[column]
        print(dataset[column].attrs)

    #add latitude and longitude for the numerical layers
    for column, raster in numerical_raster_layers.items():
        dataset[column] = (['latitude', 'longitude'], raster)
        

    dataset.latitude.attrs['standard_name'] = 'latitude'
    dataset.latitude.attrs['units'] = 'degrees_north'
    dataset.longitude.attrs['standard_name'] = 'longitude'
    dataset.longitude.attrs['units'] = 'degrees_east'

    # Set the CRS as an attribute
    dataset.attrs['proj:epsg'] = str(gdf.crs)
    dataset.attrs['bounding_box'] = str(gdf.total_bounds)
    dataset.attrs['resolution'] = resolution

    latitudeattrs = {'_CoordinateAxisType': 'Lat', 
                        'axis': 'Y', 
                        'long_name': 'latitude', 
                        'max': dataset.latitude.values.max(), 
                        'min': dataset.latitude.values.min(), 
                        'standard_name': 'latitude', 
                        'step': (dataset.latitude.values.max() - dataset.latitude.values.min()) / dataset.latitude.values.shape[0], 
                        'units': 'degrees_north'
        }
    longitudeattrs = {'_CoordinateAxisType': 'Lon', 
                    'axis': 'X', 
                    'long_name': 'longitude',
                    'max': dataset.longitude.values.max(),
                    'min': dataset.longitude.values.min(),
                    'standard_name': 'longitude', 
                    'step': (dataset.longitude.values.max() - dataset.longitude.values.min()) / dataset.longitude.values.shape[0], 
                    'units': 'degrees_east'
    }
    dataset.latitude.attrs = latitudeattrs
    dataset.longitude.attrs = longitudeattrs
    dataset.attrs['epsg : proj'] = 4326
    dataset.attrs['resolution'] = resolution
   
    zarr_path = f"{arco_asset_temp_dir}/{title}_res{resolution}.zarr"
    dataset.to_zarr(zarr_path, mode = 'w')
    print(f'{title} zarr made at {zarr_path}')
    
    return zarr_path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python shp_to_zarr.py <URL>")
        sys.exit(1)
    
    zip_url = sys.argv[1]
    arco_asset_temp_dir = os.environ.get('ARCO_ASSET_TEMP_DIR')
    
    # Download and extract the zip file, then get the path to the .shp file
    shp_file_path = download_and_extract_zip(zip_url)
    
    print(shp_file_path)
    permissions = stat.filemode(os.stat(shp_file_path).st_mode)
    print("File Permissions:", permissions)
    # Convert the .shp file to zarr using gdf2zarrconverter function
    if shp_file_path:
        zarr_path = gdf2zarrconverter(shp_file_path, arco_asset_temp_dir)
        print(f"Zarr file created: {zarr_path}")
    else:
        print("No .shp file found in the downloaded zip file.")
