# Credits — Water U-Net (backend/water)

| Source | Used for | Credit / licence |
|---|---|---|
| **NISAR** L2 GCOV (NASA/ISRO), provisional and V1 products, distributed by the **ASF DAAC** | HH/HV backscatter, all NISAR results | NASA/JPL and ISRO. NASA Earthdata data are openly shared without restriction (NASA Earth Science Data and Information Policy). |
| **OPERA DSWx-HLS** (NASA/JPL), distributed by **PO.DAAC** | Optical water reference, DEM layer (B10) for diagnostics | NASA/JPL-Caltech OPERA project; open NASA data. |
| **HLS** (Harmonized Landsat Sentinel-2), **LP DAAC** | Same-date true-colour diagnostic panels | NASA LP DAAC; contains Landsat (USGS/NASA) and modified Copernicus Sentinel-2 data. |
| **Sen1Floods11** (Bonafilia, Tellman, Anderson, Issenberg, CVPR Workshops 2020, pp. 210-211), `gs://sen1floods11` | Training and Sentinel-1 test / Bolivia hold-out of the U-Net | Cited as the authors request. The repository (github.com/cloudtostreet/Sen1Floods11) states no explicit licence; the chips contain modified Copernicus Sentinel-1 data (Copernicus open-access licence). |
| **Esri World Imagery** basemap (sources at the reservoir: Vantor/WorldView-3 2025-04-27, WorldView-2 2023-01-05; Earthstar Geographics) | Background of slide figures only | "Basemap: Esri, Vantor, Earthstar Geographics, and the GIS User Community". Esri terms of use. |
| **OpenStreetMap** (Overpass API) | Reservoir extents for the areas of interest | © OpenStreetMap contributors, ODbL. |
| segmentation_models_pytorch, PyTorch, torchvision ResNet-34 ImageNet weights | Model | MIT / BSD licences. |
| rasterio, GDAL, h5py, earthaccess, fsspec, scikit-image, contextily, matplotlib | Processing and figures | Open-source licences (BSD/MIT/Apache). |
