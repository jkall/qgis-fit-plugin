# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FIT
                                 A QGIS plugin
 Import FIT files from training devices
                             -------------------
        begin                : 2021-06-07
        copyright            : (C) 2021 by Josef K
        email                : groundwatergis@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load FIT class from file FIT.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .fit import FIT
    return FIT(iface)
