# QGIS FIT plugin
A QGIS plugin for importing [FIT files](https://developer.garmin.com/fit/protocol/) from training devices. 

The plugin is so far only tested reported with FIT files from devices:
 * Garmin forerunner 935

Activities, sessions and locations from the training device are imported to a spatialite database, and optionally converted to gpx and csv files.  

The FIT plugin, released as free software under GNU General Public License, includes major parts of the  [python fitparse module](https://github.com/dtcooper/python-fitparse) which is released under the MIT License.  

_Copyright (c) 2021 [josef k](https://github.com/jkall/)_
