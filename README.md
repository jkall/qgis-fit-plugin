# QGIS FIT plugin
A QGIS plugin for importing [FIT files](https://developer.garmin.com/fit/protocol/) from training devices. The FIT file parsing is performed by the [python fitparse module](https://github.com/dtcooper/python-fitparse) which is included in the plugin. 

Activities, sessions and locations may be imported from the training device into a spatialite database. Optionally also converted to gpx and csv files. The plugin also includes a simple feature to create some basic plots of speed, altitude, heartrate etc. and also visualize speed on the map. 

The plugin is so far only tested with FIT files from the following devices:
 * Garmin Edge 500
 * Garmin Edge 810
 * Garmin Edge 820
 * Garmin fenix 2
 * Garmin fenix 5
 * Garmin forerunner 110
 * Garmin forerunner 935
 * Garmin vivoactive HR
 * Speedcoach GPS

Please report successful usage from any other devices. 

See the [wiki](https://github.com/jkall/qgis-fit-plugin/wiki) for instructions on how to use the plugin.  

The FIT plugin is released as free software under GNU General Public License. The included [python fitparse module](https://github.com/dtcooper/python-fitparse) is released under the MIT License.  

_Copyright (c) 2021 [josef k](https://github.com/jkall/)_
