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
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QApplication
from qgis.utils import iface
from qgis.core import Qgis, QgsDataSourceUri, QgsVectorLayer, QgsProject, QgsClassificationQuantile, QgsRendererRangeLabelFormat, QgsStyle, QgsGraduatedSymbolRenderer, QgsMarkerSymbol, QgsCoordinateTransform #, QgsClassificationEqualInterval

from .fit_dialog import FITDialog

import datetime, os, sys, tempfile, time, sqlite3, webbrowser, configparser
import xml.dom.minidom as minidom
import xml.etree.cElementTree as ET
try:
    import pandas as pd
    pandasloaded = True
except:
    pandasloaded = False
import matplotlib.pyplot as plt

try:
    from qgis.utils import spatialite_connect
    pyspatialite=True
except:
    pass
    pyspatialite=False

#add plugin directory to pythonpath (needed here to allow importing the module from subfolders)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/fitparse'))
from fitparse.base import FitFile

class FIT:

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FIT_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FIT')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FIT', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(os.path.dirname(__file__), "icons","fit.png")
        self.add_action(
            icon_path,
            text=self.tr(u'import FIT files'),
            callback=self.opendialog,
            parent=self.iface.mainWindow())

        icon_path = os.path.join(os.path.dirname(__file__), "icons", "analyze.png")
        self.add_action(
            icon_path,
            text=self.tr(u'analyze session/track'),
            callback=self.analyze,
            parent=self.iface.mainWindow())

        icon_path = os.path.join(os.path.dirname(__file__), "icons", "help.png")
        self.add_action(
            icon_path,
            text=self.tr(u'help'),
            add_to_toolbar=False,
            callback=self.help,
            parent=self.iface.mainWindow())

        # will be set False in import_fit()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&FIT'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_database(self):
        self.db = QFileDialog.getSaveFileName(None, 'Select database (will be created if not exists)', '', "Spatialite db (*.sqlite)", options=QFileDialog.DontConfirmOverwrite)
        self.dlg.database_filepath.setText(str(self.db[0]))

    def select_output_folder(self): 
        self.output_folder = str(QFileDialog.getExistingDirectory(None, "Select Directory"))
        self.dlg.output_folder.setText(self.output_folder)

    def select_input_files(self): 
        # getOpenFileNames returns a tuple and the first position contains a list with full path to each of the selected files
        self.input_files = QFileDialog().getOpenFileNames(None, "Select input files ","", 'FIT files (*.FIT *.fit)')
        self.inp_files_list=[]
        for file in self.input_files[0]: 
            self.inp_files_list.append(os.path.basename(file))
        self.dlg.input_files.setText(','.join(self.inp_files_list))

    def create_database_tables(self):
        sqlitestring='''SELECT InitSpatialMetadata('WGS84');
        CREATE TABLE IF NOT EXISTS "activities" ("filename" TEXT,"garmin_product" TEXT, "time_created" TEXT,"name" TEXT, "num_sessions" INTEGER, "sport" TEXT,"sub_sport" TEXT,  "timestamp_local" TIMESTAMP,"timestamp_utc" TIMESTAMP UNIQUE,"total_timer_time" REAL, PRIMARY KEY (filename));
        CREATE TABLE IF NOT EXISTS "sessions" ("avg_cadence" INTEGER, "avg_heart_rate" INTEGER, "avg_speed" REAL, "avg_temperature" INTEGER, "enhanced_avg_speed" REAL,     "enhanced_max_speed" REAL, "filename" TEXT, "max_cadence" INTEGER, "max_heart_rate" INTEGER, "max_speed" REAL, "max_temperature" INTEGER, "name" TEXT, "sport"  TEXT, "start_position_lat" REAL, "start_position_lon" REAL, "start_time_local" TIMESTAMP, "start_time_utc" TIMESTAMP, "sub_sport" TEXT, "timestamp"    TIMESTAMP, "total_anaerobic_effect" REAL, "total_ascent" INTEGER, "total_calories" INTEGER, "total_descent" INTEGER, "total_distance" REAL, "total_elapsed_time"   REAL, "total_timer_time" REAL, "total_training_effect" REAL, PRIMARY KEY (start_time_utc), FOREIGN KEY(filename) REFERENCES activities(filename));
        SELECT AddGeometryColumn('sessions', 'geom', 4326, 'POINT', 'XY', 0);
        CREATE TABLE IF NOT EXISTS "tracks" ("start_time_utc" TIMESTAMP, "name" TEXT, "type" TEXT, "cmt" TEXT, "src" TEXT, PRIMARY KEY (start_time_utc), FOREIGN KEY    (start_time_utc) REFERENCES sessions(start_time_utc));
        SELECT AddGeometryColumn('tracks', 'geom', 4326, 'LINESTRING', 'XY', 0);
        CREATE TABLE IF NOT EXISTS "trackpoints" ("start_time_utc" TIMESTAMP, "timestamp" TIMESTAMP, "heartrate" REAL, "temperature" REAL, "cadence" REAL, "position_lat"   REAL, "position_lon" REAL, "altitude" REAL, "distance" REAL, "speed" REAL, "vertical_speed" REAL, PRIMARY KEY (timestamp), FOREIGN KEY(start_time_utc) REFERENCES     sessions(start_time_utc));
        SELECT AddGeometryColumn('trackpoints', 'geom', 4326, 'POINT', 'XY', 0);
        CREATE TABLE IF NOT EXISTS "locations" ("fid" INTEGER, "name" TEXT, "ele" REAL, "sym" TEXT, "time" TIMESTAMP, "cmt" TEXT, "unknown_5" TEXT, "unknown_6" TEXT, "unknown_253" TEXT, "unknown_254" TEXT, "src" TEXT, geom UNIQUE, PRIMARY KEY("fid"));
        SELECT RecoverGeometryColumn('locations', 'geom', 4326, 'POINT', 'XY');
        CREATE TRIGGER IF NOT EXISTS "ggi_locations_latlon_unique" BEFORE INSERT ON "locations" WHEN exists(SELECT "fid" FROM "locations" WHERE st_distance("geom", new."geom") < 0.00001) BEGIN select raise(IGNORE); END;
        CREATE TABLE IF NOT EXISTS "layer_styles"(id INTEGER PRIMARY KEY AUTOINCREMENT,f_table_catalog varchar(256),f_table_schema varchar(256),f_table_name varchar(256),f_geometry_column varchar(256),styleName text,styleQML text,styleSLD text,useAsDefault boolean,description text,owner varchar(30),ui text,update_time timestamp DEFAULT CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO layer_styles select * from layer_styles_by_plugin;
        '''
        #CREATE TABLE IF NOT EXISTS "layer_styles"(id INTEGER PRIMARY KEY AUTOINCREMENT,f_table_catalog varchar(256),f_table_schema varchar(256),f_table_name varchar(256),f_geometry_column varchar(256),styleName text,styleQML text,styleSLD text,useAsDefault boolean,description text,owner varchar(30),ui text,update_time timestamp DEFAULT CURRENT_TIMESTAMP);

        # Read layer_styles file and change paths to installation folder for plugin 
        newlayerstylesfile = open(os.path.join(tempfile.gettempdir(),"layer_styles.csv"), "w+")
        with open(os.path.join(os.path.dirname(__file__),"defs", "layer_styles_template.csv"), "r") as file:
            filedata = file.read()
        newlayerstylesfile.write(filedata.replace('SET_RELEVANT_PATH/', os.path.join(os.path.dirname(__file__), 'svg')+ os.sep))   # Notice last os.sep to also  replace the final separator 
        newlayerstylesfile.close()

        # create tables in database and fill layer styles table 
        with spatialite_connect(str(self.db[0])) as conn:
            cur = conn.cursor()
            pd.read_csv(os.path.join(tempfile.gettempdir(),"layer_styles.csv"),sep=';').to_sql("layer_styles_by_plugin", conn, if_exists='replace', index=False) # ERROR TypeError: no columns to parse from
            cur.executescript(sqlitestring)

        # remove temporary layer styles file 
        try:
            os.remove(os.path.join(tempfile.gettempdir(),"layer_styles.csv"))
        except OSError:
            pass
            
    def prettify(self,elem):
        """Return a pretty-printed XML string for the Element.
        """
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="\t")
    
    def getfromfit_spec_message_field_name_value(self,fitfile,type,fieldname):
        for message in fitfile.get_messages(type):
            return message.get_value(fieldname)

    def getfromfit_concatenated_spec_message_field_name_value(self,fitfile,type,fieldname):
        result=''
        for message in fitfile.get_messages(type): 
            result += '_{}'.format(message.get_value(fieldname))
        return result

    def semicircles2degrees(self,semicircles):
        # garmin stores coordinates in "semicircles" instead of degrees
        try:
            return semicircles * ( 180 / pow(2.0,31) )
        except:
            return None

    def elevationconversion(self,garminaltitude):
        # garmin stores elevation in something that seems like A/D levels from the baro, must be converted 
        try:
            return garminaltitude / 5 - 500
        except:
            return None

    def write2gpx(self,sessions,trackpoints,infile):
        track_no = 0
        for session_start_time in sessions['start_time_utc']:
            # Prepare elements and fields for gpx file
            root = ET.Element("gpx")
            root.set("xmlns","http://www.topografix.com/GPX/1/1")
            root.set("version","1.1")

            # create a track object for gpx file
            track = ET.SubElement(root, "trk")
            name = ET.SubElement(track,"name")
            name.text=str(sessions['name'][track_no])  # TRACK NAME

            sport = ET.SubElement(track,"type")
            sport.text=str(sessions['sport'][track_no]) # TRACK SPORT

            source_file = ET.SubElement(track,"src")
            source_file.text=os.path.basename(infile) # TRACK ORIGINAL FIT FILE NAME

            cmt = ET.SubElement(track,"cmt")
            cmt.text=str('created by fit2gpx.py')  # TRACK SILLY REMARK

            segment=ET.SubElement(track, "trkseg")
            ext=ET.SubElement(track,"extensions")
            start_time_utc=ET.SubElement(ext,"start_time_utc") # start_time_utc TRACK PRIMARY KEY = FK to PK IN sessions table
            start_time_utc.text=sessions['start_time_utc'][track_no].strftime("%Y-%m-%dT%H:%M:%S") 

            tp_no = 0
            for tp in trackpoints['timestamp']:
                if not tp==None and tp>=session_start_time and tp<=sessions['timestamp'][track_no]:
                    point=ET.SubElement(segment, "trkpt")
                    # begin with standard gpx fields
                    t=ET.SubElement(point, "time")
                    t.text=tp.strftime("%Y-%m-%dT%H:%M:%S")

                    # extension fields 
                    ext=ET.SubElement(point,"extensions") 
                    if trackpoints['heartrate'][tp_no]:
                        bpm=ET.SubElement(ext,"heartrate")
                        bpm.text=str(trackpoints['heartrate'][tp_no])
                    if trackpoints['temperature'][tp_no]: 
                        ture=ET.SubElement(ext, "temperature")
                        ture.text=str(trackpoints['temperature'][tp_no])
                    if trackpoints['cadence'][tp_no]: 
                        cad=ET.SubElement(ext, "cadence")
                        cad.text=str(trackpoints['cadence'][tp_no])

                    if trackpoints['position_lon'][tp_no] and trackpoints['position_lat'][tp_no]:
                        point.set("lat",str(trackpoints['position_lat'][tp_no])) 
                        point.set("lon",str(trackpoints['position_lon'][tp_no])) 
                        if trackpoints['altitude'][tp_no]:
                            altitude=ET.SubElement(point, "ele")
                            altitude.text=str(trackpoints['altitude'][tp_no])
                        if trackpoints['speed'][tp_no]: 
                            s=ET.SubElement(ext, "speed")
                            s.text=str(trackpoints['speed'][tp_no])
                        if trackpoints['distance'][tp_no]: 
                            d=ET.SubElement(ext, "distance")
                            d.text=str(trackpoints['distance'][tp_no])
                        if trackpoints['vertical_speed'][tp_no]: 
                            vert=ET.SubElement(ext, "vertical_speed")
                            vert.text=str(trackpoints['vertical_speed'][tp_no])
                tp_no +=1

            # --------------- write gpx output file - ----------------------------------
            output_file = sessions['start_time_utc'][track_no].strftime("%Y%m%dT%H%M%S") + '.gpx'
            output_file = os.path.abspath(os.path.join(os.sep, self.output_folder, output_file))
            f = open(output_file, 'w+')
            f.write(self.prettify(root))
            f.close()
            track_no += 1

    def wpt2gpx(self,df, gpxfilename): 
        root = ET.Element("gpx")
        root.set("xmlns","http://www.topografix.com/GPX/1/1")
        root.set("version","1.1")
        wpt_no = 0
        for wpt in df['name']:
            wpt = ET.SubElement(root, "wpt")
            wpt.set("lat",str(df['latitude'][wpt_no])) 
            wpt.set("lon",str(df['longitude'][wpt_no])) 
            name = ET.SubElement(wpt,"name")
            name.text=str(df['name'][wpt_no])
            ele = ET.SubElement(wpt,"ele")
            ele.text=str(df['ele'][wpt_no])
            sym = ET.SubElement(wpt,"sym")
            sym.text=str(df['sym'][wpt_no])
            src = ET.SubElement(wpt,"src")
            src.text=str(df['src'][wpt_no])
            wpt_no +=1
        output_file = os.path.abspath(os.path.join(os.sep, self.output_folder, gpxfilename))
        f = open(output_file, 'w+')    
        f.write(self.prettify(root))
        f.close()

    def write2csv(self, df, csvfname): 
        activities_filename = os.path.abspath(os.path.join(os.sep, self.output_folder, csvfname))
        with open(activities_filename, 'a') as f:
            df.to_csv(f, index=False, sep=';', encoding='utf-8-sig', mode='a', header=f.tell()==0)

    def write2sqlite(self, activities_df, sessions_df, tracks_df, trackpoints_df):
        with spatialite_connect(self.db[0]) as conn:
            activities_df.to_sql('temptable', conn, if_exists='append', index=False)
            cur = conn.cursor()
            cur.executescript('''INSERT OR IGNORE INTO activities("filename","garmin_product","time_created","name", "num_sessions", "sport","sub_sport","timestamp_local","timestamp_utc","total_timer_time") SELECT "filename","garmin_product","time_created","name", "num_sessions", "sport","sub_sport","timestamp_local","timestamp_utc","total_timer_time" FROM temptable;drop table temptable;''')
            cur.executescript('''SELECT UpdateLayerStatistics('activities');''')

            sessions_df.to_sql('temptable', conn, if_exists='append', index=False)
            cur.executescript('''INSERT OR IGNORE INTO sessions ("avg_cadence", "avg_heart_rate", "avg_speed", "avg_temperature", "enhanced_avg_speed", "enhanced_max_speed", "filename", "max_cadence", "max_heart_rate", "max_speed", "max_temperature", "name", "sport", "start_position_lat", "start_position_lon", "start_time_local", "start_time_utc", "sub_sport", "timestamp", "total_anaerobic_effect", "total_ascent", "total_calories", "total_descent", "total_distance", "total_elapsed_time", "total_timer_time", "total_training_effect", "geom") SELECT "avg_cadence", "avg_heart_rate", "avg_speed", "avg_temperature", "enhanced_avg_speed", "enhanced_max_speed", "filename", "max_cadence", "max_heart_rate", "max_speed", "max_temperature", "name", "sport", "start_position_lat", "start_position_lon", "start_time_local", "start_time_utc", "sub_sport", "timestamp", "total_anaerobic_effect", "total_ascent", "total_calories", "total_descent", "total_distance", "total_elapsed_time", "total_timer_time", "total_training_effect", MakePoint("start_position_lon", "start_position_lat", (select srid from geometry_columns where f_table_name = 'sessions')) as "geom" FROM temptable;drop table temptable;''')
            cur.executescript('''SELECT UpdateLayerStatistics('sessions');''')

            tracks_df.to_sql('temptable', conn, if_exists='append', index=True)
            cur.executescript('''INSERT OR IGNORE INTO tracks("start_time_utc", "name", "type", "cmt", "src", "geom") SELECT "start_time_utc", "name", "type", "cmt", "src", ST_GeomFromText('LINESTRING('||"wkt_linestring"||')', (select srid from geometry_columns where f_table_name = 'tracks')) FROM temptable;drop table temptable;''')
            cur.executescript('''SELECT UpdateLayerStatistics('tracks');''')

            trackpoints_df.to_sql('temptable', conn, if_exists='append', index=True)
            cur.executescript('''INSERT OR IGNORE INTO trackpoints("start_time_utc", "timestamp", "heartrate", "temperature", "cadence", "position_lat", "position_lon", "altitude", "distance", "speed", "vertical_speed", "geom") SELECT "start_time_utc", "timestamp", "heartrate", "temperature", "cadence", "position_lat", "position_lon", "altitude", "distance", "speed", "vertical_speed", MakePoint("position_lon", "position_lat", (select srid from geometry_columns where f_table_name = 'trackpoints')) as "geom" FROM temptable;drop table temptable;''')
            cur.executescript('''SELECT UpdateLayerStatistics('trackpoints');''')

    def wpt2sqlite(self, locations_df):
        with spatialite_connect(self.db[0]) as conn:
            locations_df.to_sql('temptable', conn, if_exists='append', index=False)
            cur = conn.cursor()
            cur.executescript('''INSERT OR IGNORE INTO locations("name", "ele", "sym", "src", "geom") SELECT "name", "ele", "sym", "src", MakePoint("longitude", "latitude", (select srid from geometry_columns where f_table_name = 'locations')) as "geom" FROM temptable;drop table temptable;''')
            cur.executescript('''SELECT UpdateLayerStatistics('locations');''')

    def loadLCTNSFIT(self,infile):
        iconsymdict={4 : 'Bank',  7 : 'Boat Ramp',  11 : 'Campground',  12 : 'Car',  23 : 'Crossing',  83 : 'Flag, Blue',  81 : 'Geocache',  52 : 'Parking Area',  54 : 'Picnic Area',  58 : 'Residence',  71 : 'Summit',  72 : 'Swimming Area',  88 : 'Beacon',  126 : 'Food Source'} 

        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(infile)
        infilename_and_filedate= '{} {}'.format(os.path.basename(infile),time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(mtime)))
        # Load the FIT file
        fitfile = FitFile(infile)
        locations={'name':[], 'latitude':[], 'longitude':[], 'ele':[], 'sym':[], 'unknown_5':[],'unknown_6':[], 'unknown_253':[],'unknown_254':[], 'src':[]}
        loc_no = 0
        for location in fitfile.get_messages('unknown_29'):
            # set all values to None
            for key in locations.keys():
                locations[key].append(None)
            for loc_data in location:
                if loc_data.name=='unknown_0': locations['name'][loc_no]=loc_data.value; continue;
                if loc_data.name=='unknown_1': locations['latitude'][loc_no]=self.semicircles2degrees(loc_data.value); continue;
                if loc_data.name=='unknown_2': locations['longitude'][loc_no]=self.semicircles2degrees(loc_data.value); continue;
                if loc_data.name=='unknown_3': locations['sym'][loc_no]=iconsymdict.get(loc_data.value,'Flag, Blue'); continue;
                if loc_data.name=='unknown_4': locations['ele'][loc_no]=self.elevationconversion(loc_data.value); continue;
                if loc_data.name=='unknown_5': locations['unknown_5'][loc_no]=loc_data.value; continue;
                if loc_data.name=='unknown_6': locations['unknown_6'][loc_no]=loc_data.value; continue;
                if loc_data.name=='unknown_253': locations['unknown_253'][loc_no]=loc_data.value; continue;
                if loc_data.name=='unknown_254': locations['unknown_254'][loc_no]=loc_data.value; continue;
            locations['src'][loc_no]=infilename_and_filedate
            loc_no += 1
        locations_df = pd.DataFrame(locations)
        if hasattr(self, 'output_folder') and  len(self.output_folder)>0: # to gpx and csv
            # to csv
            self.write2csv(locations_df, 'locations.csv')
            # create gpx file with waypoints from the locations
            self.wpt2gpx(locations_df, 'locations.gpx')
            self.gpxcounts +=1
        
        if hasattr(self, 'db') and  len(str(self.db[0]))>0: # to sqlite
            self.wpt2sqlite(locations_df)
            self.sqlitecounts +=1

    def fit2gpx_and_sqlite(self, infile): 
        # Load the FIT file
        fitfile = FitFile(infile)
        # ------------------- activities -------------------------------
        activities={}

        file_id_type = self.getfromfit_spec_message_field_name_value(fitfile,'file_id','type')
        if  file_id_type == 8: # If locations file!
            self.loadLCTNSFIT(infile)
            return
        elif not file_id_type =='activity':# or file_id_type == 4:
            iface.messageBar().pushMessage("Alert!", "Only FIT files containing activities and locations are supported!", level=Qgis.Critical, duration=5)
            iface.messageBar().pushMessage("Alert!", 'Hamlet says, "something is rotten in the state of FIT": {}'.format(infile), level=Qgis.Critical, duration=15)
            return
        else:
            pass
        activities['filename'] = os.path.basename(infile)
        activities['garmin_product']=self.getfromfit_spec_message_field_name_value(fitfile,'file_id','garmin_product')
        activities['time_created']=self.getfromfit_spec_message_field_name_value(fitfile,'file_id','time_created')
        activities['num_sessions']=self.getfromfit_spec_message_field_name_value(fitfile,'activity','num_sessions')
        activities['timestamp_utc']=self.getfromfit_spec_message_field_name_value(fitfile,'activity','timestamp')
        activities['timestamp_local']=self.getfromfit_spec_message_field_name_value(fitfile,'activity','local_timestamp')
        try:
            offset = activities.get("timestamp_local") - activities.get("timestamp_utc")
        except:
            offset = 0
        if isinstance(offset, int):
            offset = datetime.timedelta(offset)

        activities['total_timer_time']=self.getfromfit_spec_message_field_name_value(fitfile,'activity','total_timer_time')
        try:
            numsessions = self.getfromfit_spec_message_field_name_value(fitfile,'activity','num_sessions')
        except: # for corrupt files where the sessions message type is missing
            numsessions = 0 
        if numsessions:
            if numsessions  > 1:
                activities['name']='Multisport_{}'.format(self.getfromfit_concatenated_spec_message_field_name_value(fitfile,'sport','name'))
                activities['sport']=self.getfromfit_concatenated_spec_message_field_name_value(fitfile,'sport','sport')
                activities['sub_sport']=self.getfromfit_concatenated_spec_message_field_name_value(fitfile,'sport','sub_sport')
            else:
                activities['name']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','name')
                activities['sport']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','sport')
                activities['sub_sport']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','sub_sport')
        else: # fix for broken FIT files where sessions are missing
            numsessions = 0 
            activities['name']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','name')
            activities['sport']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','sport')
            activities['sub_sport']=self.getfromfit_spec_message_field_name_value(fitfile,'sport','sub_sport')

        # ------------------- sessions (and tracks) fields for destination tables -------------------------------
        sessions={'filename':[], 'name':[], 'start_time_local':[], 'avg_cadence':[], 'avg_heart_rate':[], 'avg_speed':[], 'avg_temperature':[], 'enhanced_avg_speed':[], 'enhanced_max_speed':[], 'max_cadence':[], 'max_heart_rate':[], 'max_speed':[], 'max_temperature':[], 'sport':[], 'start_position_lat':[], 'start_position_lon':[], 'start_time_utc':[], 'sub_sport':[], 'timestamp':[], 'total_anaerobic_effect':[], 'total_ascent':[], 'total_calories':[], 'total_descent':[], 'total_distance':[], 'total_elapsed_time':[], 'total_timer_time':[], 'total_training_effect':[], 'start_time_local':[]}

        session_no = 0
        for session in fitfile.get_messages('session'):
            # set all values to None
            for key in sessions.keys():
                sessions[key].append(None)

            for session_data in session:
                sessions['filename'][session_no]=os.path.basename(infile);
                if session_data.name=='unknown_110': sessions['name'][session_no]=session_data.value; continue;
                if session_data.name=='avg_cadence': sessions['avg_cadence'][session_no]=session_data.value; continue;
                if session_data.name=='avg_heart_rate': sessions['avg_heart_rate'][session_no]=session_data.value; continue;
                if session_data.name=='avg_speed': sessions['avg_speed'][session_no]=session_data.value; continue;
                if session_data.name=='avg_temperature': sessions['avg_temperature'][session_no]=session_data.value; continue;
                if session_data.name=='enhanced_avg_speed': sessions['enhanced_avg_speed'][session_no]=session_data.value; continue;
                if session_data.name=='enhanced_max_speed': sessions['enhanced_max_speed'][session_no]=session_data.value; continue;
                if session_data.name=='max_cadence': sessions['max_cadence'][session_no]=session_data.value; continue;
                if session_data.name=='max_heart_rate': sessions['max_heart_rate'][session_no]=session_data.value; continue;
                if session_data.name=='max_speed': sessions['max_speed'][session_no]=session_data.value; continue;
                if session_data.name=='max_temperature': sessions['max_temperature'][session_no]=session_data.value; continue;
                if session_data.name=='sport': sessions['sport'][session_no]=session_data.value; continue;
                if session_data.name=='start_position_lat': sessions['start_position_lat'][session_no]=self.semicircles2degrees(session_data.value); continue;
                if session_data.name=='start_position_long': sessions['start_position_lon'][session_no]=self.semicircles2degrees(session_data.value); continue;
                if session_data.name=='start_time': sessions['start_time_utc'][session_no]=session_data.value; continue;
                if session_data.name=='sub_sport': sessions['sub_sport'][session_no]=session_data.value; continue;
                if session_data.name=='timestamp': sessions['timestamp'][session_no]=session_data.value; continue;
                if session_data.name=='total_anaerobic_training_effect': sessions['total_anaerobic_effect'][session_no]=session_data.value; continue;
                if session_data.name=='total_ascent': sessions['total_ascent'][session_no]=session_data.value; continue;
                if session_data.name=='total_calories': sessions['total_calories'][session_no]=session_data.value; continue;
                if session_data.name=='total_descent': sessions['total_descent'][session_no]=session_data.value; continue;
                if session_data.name=='total_distance': sessions['total_distance'][session_no]=session_data.value; continue;
                if session_data.name=='total_elapsed_time': sessions['total_elapsed_time'][session_no]=session_data.value; continue;
                if session_data.name=='total_timer_time': sessions['total_timer_time'][session_no]=session_data.value; continue;
                if session_data.name=='total_training_effect': sessions['total_training_effect'][session_no]=session_data.value; continue;
            if sessions['start_time_utc'][session_no]:
                sessions['start_time_local'][session_no]=sessions['start_time_utc'][session_no] + offset

            session_no += 1

        if numsessions==0: # sessions may be missing in corrupt FIT files so we need to create one dummy instance and collect some much needed records
            for key in sessions.keys():
                sessions[key].append(None)
            sessions['filename'][0]=os.path.basename(infile)
            sessions['timestamp'][0]=datetime.datetime.strptime('2099-01-01','%Y-%m-%d')# set to very late date just to catch all records in condition below, will be adjusted later...
            sessions['start_time_utc'][0]=activities['time_created'] # we set start_time_utc to the time when file was created, as an approximation

        # Now, create a track (including a gpx file) for each session we found in the FIT file
        tracks={'start_time_utc':[], 'name':[], 'type':[], 'cmt':[], 'src':[], 'wkt_linestring':[]}
        trackpoints={'start_time_utc':[], 'timestamp':[], 'heartrate':[],'temperature':[], 'cadence':[], 'position_lat':[], 'position_lon':[], 'altitude':[], 'distance':[], 'speed':[], 'vertical_speed':[]}

        track_no = 0
        for session_start_time in sessions['start_time_utc']:
            # create a track object
            tracks['name'].append(sessions['name'][track_no])
            tracks['type'].append(sessions['sport'][track_no])
            tracks['src'].append(os.path.basename(infile))
            tracks['cmt'].append('created by FIT plugin for QGIS')
            tracks['start_time_utc'].append(sessions['start_time_utc'][track_no])
            tracks['wkt_linestring'].append('')

            #------------------ records = trackpoints ------------------------------------------------
            record_no = 0
            for records in fitfile.get_messages('record'): 
                r_altitude=None
                r_cadence=None
                r_distance=None
                r_enhanced_altitude=None
                r_enhanced_speed=None
                r_heartrate=None
                r_position_lat=None
                r_position_lon=None
                r_speed=None
                r_temperature=None
                r_timestamp=None
                r_vertical_speed=None

                for record_data in records: 
                        if record_data.name=='timestamp': r_timestamp=record_data.value; continue;
                        if not (type(record_data.value) is int or type(record_data.value) is float): 
                            continue # if non-numerial, we are not interested, then go to nex iteration!
                        if record_data.name=='position_lat': r_position_lat=round(self.semicircles2degrees(record_data.value),10); continue;
                        if record_data.name=='position_long': r_position_lon=round(self.semicircles2degrees(record_data.value),10); continue;
                        if record_data.name=='altitude': r_altitude=round(record_data.value,1); continue;
                        if record_data.name=='enhanced_altitude': r_enhanced_altitude=round(record_data.value,1); continue;
                        if record_data.name=='enhanced_speed': r_enhanced_speed=round(record_data.value,3); continue;
                        if record_data.name=='speed': r_speed=round(record_data.value,3); continue;
                        if record_data.name=='cadence': r_cadence=record_data.value; continue;
                        if record_data.name=='distance': r_distance=record_data.value; continue;
                        if record_data.name=='heart_rate': r_heartrate=round(record_data.value,0); continue;
                        if record_data.name=='temperature': r_temperature=record_data.value; continue;
                        if record_data.name=='vertical_speed': r_vertical_speed=record_data.value; continue;

                # if we have a timestamp, then store as a trackpoint
                # also we need to check whether this record belongs to current session (i.e. r_timestamp is witin time span for this session)
                # due to some corrupt FIT files we also need to search for first tiestamp...
                if not r_timestamp==None:
                    if r_timestamp>=session_start_time and r_timestamp<=sessions['timestamp'][track_no]:
                        trackpoints['timestamp'].append(r_timestamp)
                        trackpoints['start_time_utc'].append(sessions['start_time_utc'][track_no])
                        trackpoints['heartrate'].append(r_heartrate)
                        trackpoints['temperature'].append(r_temperature)
                        trackpoints['cadence'].append(r_cadence)
                        trackpoints['position_lat'].append(r_position_lat)  
                        trackpoints['position_lon'].append(r_position_lon)
                        if r_position_lat and r_position_lon:
                            tracks['wkt_linestring'][track_no]=tracks['wkt_linestring'][track_no]+'{} {},'.format(str(r_position_lon),str(r_position_lat))# terrible terrible method of  adding coordinate pairs to wkt linestring
                            if numsessions==0 and not sessions['start_position_lat'][0]  and not sessions['start_position_lon'][0]: # for a corrupt FIT file: catch first coordinate pairs as start pos for session
                                sessions['start_position_lat'][0]=r_position_lat
                                sessions['start_position_lon'][0]=r_position_lon
                        if r_altitude:
                            trackpoints['altitude'].append(r_altitude)
                        elif r_enhanced_altitude:
                            trackpoints['altitude'].append(r_enhanced_altitude)
                        else:
                            try:
                                trackpoints['altitude'].append(elevation_data.get_elevation(r_position_lat, r_position_lon))
                            except:
                                trackpoints['altitude'].append(None)
                        if r_speed: 
                            trackpoints['speed'].append(r_speed)
                        else:
                            trackpoints['speed'].append(r_enhanced_speed)
                        trackpoints['distance'].append(r_distance)
                        trackpoints['vertical_speed'].append(r_vertical_speed)

                record_no +=1

            tracks['wkt_linestring'][track_no]=tracks['wkt_linestring'][track_no][:len(tracks['wkt_linestring'][track_no])-1]#ugly hack to get rid of last comma
            track_no += 1

        if numsessions==0: # fixes for a  corrupt FIT file
            try: # if there actually were some recorded trackpoints, take the last record timestamp for the session
                sessions['timestamp'][0]=trackpoints['timestamp'][len(trackpoints['timestamp'])-1]
            except: # else just leave the session timestamp as is 
                pass

        #-------------------  CREATE DATAFRAMES AND WRITE TO CSV AND SQLITE ---------------------------------------------
        activities_df = pd.DataFrame(activities,index=[0])
        sessions_df = pd.DataFrame(sessions)
        tracks_df = pd.DataFrame.from_dict(tracks,orient='index')
        tracks_df = tracks_df.transpose()

        trackpoints_df = pd.DataFrame.from_dict(trackpoints,orient='index')#,index=[1])
        trackpoints_df = trackpoints_df.transpose()

        if hasattr(self, 'output_folder') and  len(self.output_folder)>0: # to gpx and csv
            self.write2csv(activities_df, 'activities.csv')
            self.write2csv(sessions_df, 'sessions.csv')
            self.write2gpx(sessions, trackpoints, infile)
            self.gpxcounts += 1

        if hasattr(self, 'db') and  len(str(self.db[0]))>0: # to sqlite
            self.write2sqlite(activities_df, sessions_df, tracks_df, trackpoints_df)
            self.sqlitecounts += 1

    def opendialog(self):
        if not pandasloaded:
            iface.messageBar().pushMessage("Error!", "Sorry, you need python3-pandas to use this plugin!", level=Qgis.Critical, duration=10)
            return
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = FITDialog()
            self.dlg.toolButtonImportFolder.clicked.connect(self.select_input_files)
            self.dlg.toolButtonOutputFolder.clicked.connect(self.select_output_folder)
            self.dlg.toolButtonDB.clicked.connect(self.select_database)

        try:
            self.dlg.input_files.setText(','.join(self.inp_files_list))
        except:
            self.dlg.input_files.setText('select activity and/or locations FIT files')
        try:
            self.dlg.output_folder.setText(self.output_folder)
        except:
            self.dlg.output_folder.setText('for gpx and csv files')
        try:
            self.dlg.database_filepath.setText(str(self.db[0]))
        except:
            self.dlg.database_filepath.setPlaceholderText( "e.g. " + os.path.join(os.path.expanduser("~"), "fit_db.sqlite"))


        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            self.import_fit()

    def get_tables(self):
        sqlite_internal_tables = """('ElementaryGeometries',
                    'geom_cols_ref_sys',
                    'geometry_columns',
                    'geometry_columns_time',
                    'spatial_ref_sys',
                    'spatial_ref_sys_aux',
                    'spatial_ref_sys_all',
                    'spatialite_history',
                    'vector_layers',
                    'views_geometry_columns',
                    'virts_geometry_columns',
                    'geometry_columns_auth',
                    'geometry_columns_fields_infos',
                    'geometry_columns_field_infos',
                    'geometry_columns_statistics',
                    'sql_statements_log',
                    'layer_statistics',
                    'sqlite_sequence',
                    'sqlite_stat1',
                    'sqlite_stat3',
                    'views_layer_statistics',
                    'virts_layer_statistics',
                    'vector_layers_auth',
                    'vector_layers_field_infos',
                    'vector_layers_statistics',
                    'views_geometry_columns_auth',
                    'views_geometry_columns_field_infos',
                    'views_geometry_columns_statistics',
                    'virts_geometry_columns_auth',
                    'virts_geometry_columns_field_infos',
                    'virts_geometry_columns_statistics' ,
                    'geometry_columns',
                    'spatialindex',
                    'SpatialIndex')"""
        tables_sql = ("""SELECT tbl_name FROM sqlite_master WHERE type='table' AND tbl_name NOT IN %s ORDER BY tbl_name""" % (sqlite_internal_tables))
        with spatialite_connect(self.db[0]) as conn:
                cur = conn.cursor()
                cur.execute(tables_sql)
                tables_in_db = cur.fetchall() 
        tablenames = [col[0] for col in tables_in_db]
        return tablenames

    def import_fit(self): # create database if needed, perform the import and export
        """Run method that performs all the real work"""
        if not(hasattr(self, 'input_files')): # stop if no FIT files are selected
            iface.messageBar().pushMessage("Alert!", "Select FIT files to import!", level=Qgis.Critical, duration=10)
            return
        if not((hasattr(self, 'output_folder') and len(self.output_folder)>0) or (hasattr(self, 'db') and len(str(self.db[0]))>0)): # stop unless export location(s) selected
            iface.messageBar().pushMessage("Alert!", "Select export folder and/or database!", level=Qgis.Critical, duration=10)
            return
            
        if hasattr(self, 'db') and  len(str(self.db[0]))>0: # Create tables in database unless they exist
            # test if the tables already exists or not
            existing_tables = self.get_tables()
            if 'layer_styles' not in existing_tables:
                if pyspatialite:
                    QApplication.setOverrideCursor(Qt.WaitCursor) #show user this may take a long time...
                    self.create_database_tables()
                    QApplication.restoreOverrideCursor() #now this long process is done and the cursor is back as normal
                else:
                    iface.messageBar().pushMessage("Alert!", "pyspatialite is missing, check your qgis installation!!!", level=Qgis.Critical, duration=10)
                    return

        # perform the imports and exports
        QApplication.setOverrideCursor(Qt.WaitCursor) #show user this may take a long time...
        self.gpxcounts=0 
        self.sqlitecounts=0

        # count features before import
        if hasattr(self, 'db') and  len(str(self.db[0]))>0:
            with spatialite_connect(self.db[0]) as conn:
                cur = conn.cursor()
                cur.execute('''select 'locations', count(*) from locations union select 'activities', count(*) from activities union select 'sessions', count(*) from sessions union select 'tracks', count(*) from tracks''')
                features_before = cur.fetchall()

        for infile in self.input_files[0]:
            if os.path.isfile(infile): # filter dirs
                #print('Processing {}'.format(infile))#debug
                iface.statusBarIface().showMessage(" processing {}".format(infile))
                self.fit2gpx_and_sqlite(infile)
        iface.statusBarIface().clearMessage()
        QApplication.restoreOverrideCursor() #now this long process is done and the cursor is back as normal

        # count features after import
        if hasattr(self, 'db') and  len(str(self.db[0]))>0:
            with spatialite_connect(self.db[0]) as conn:
                cur = conn.cursor() # not needed??
                cur.execute('''select 'locations', count(*) from locations union select 'activities', count(*) from activities union select 'sessions', count(*) from sessions union select 'tracks', count(*) from tracks''')
                features_after = cur.fetchall() 

            iface.messageBar().pushMessage("info:", "Features imported: activities={},locations={}, sessions={}, tracks={}".format(features_after[0][1] - features_before[0][1],features_after[1][1] - features_before[1][1],features_after[2][1] - features_before[2][1],features_after[3][1] - features_before[3][1]), level=Qgis.Info, duration=14)

        iface.messageBar().pushMessage("Finished!", "{} FIT files converted to gpx and {} files imported to sqlite db!".format(self.gpxcounts, self.sqlitecounts), level=Qgis.Info, duration=7)

    def analyze(self):
        # https://gis.stackexchange.com/questions/167707/connecting-qgis-spatialite-and-python/167712
        # https://gis.stackexchange.com/questions/243942/get-spatialite-database-path-from-vector-layer-in-pyqgis
        # https://www.sigterritoires.fr/index.php/en/python-methods-for-qgis-how-to-access-vector-data-postgis-spatiality/
        # https://qgis-docs.readthedocs.io/en/latest/docs/pyqgis_developer_cookbook/loadlayer.html
        provider = iface.activeLayer().dataProvider()
        kolumnindex = provider.fieldNameIndex('start_time_utc')
        if 'spatialite' in provider.description().lower() and iface.activeLayer().selectedFeatureCount()==1 and not(kolumnindex==-1):
            the_track = iface.activeLayer().selectedFeatures()[0]
            start_time_utc = the_track['start_time_utc']
            #layer_filter = '''"start_time_utc"='''+"'"+start_time_utc.toString('yyyy-MM-ddThh:mm:ss')+"'"
            layer_filter = '''"start_time_utc" like '''+"'%"+start_time_utc.toString('yyyy-MM-dd%hh:mm:ss')+"%'"
            uri = QgsDataSourceUri()
            databasepath = iface.activeLayer().dataProvider().dataSourceUri().split(' ')[0].replace('dbname=','').replace("'","")
            uri.setDatabase(databasepath)
            uri.setDataSource('','trackpoints','geom',layer_filter)
            layer = QgsVectorLayer(uri.uri(), start_time_utc.toString('yyyy-MM-ddThhmmss'), 'spatialite')
            QgsProject.instance().addMapLayer(layer)

            # zooming to layer extent
            #iface.mapCanvas().setExtent(layer.extent()) This does not work when project crs differs from layer crs!!
            # The following method works even when crs differs
            canvas = iface.mapCanvas()
            xform = QgsCoordinateTransform(layer.crs(),canvas.mapSettings().destinationCrs(),QgsProject.instance())
            canvas.setExtent(xform.transform(layer.extent()))
            canvas.refresh() 

            # SYMBOLOGY
            # https://gis.stackexchange.com/questions/342352/apply-a-color-ramp-to-vector-layer-using-pyqgis3
            ramp_name = 'Spectral'
            value_field = 'speed'
            num_classes = 5
            #You can use any of these classification method classes:
            classification_method = QgsClassificationQuantile()
            #QgsClassificationQuantile()
            #QgsClassificationEqualInterval()
            #QgsClassificationJenks()
            #QgsClassificationPrettyBreaks()
            #QgsClassificationLogarithmic()
            #QgsClassificationStandardDeviation()

            # change format settings as necessary
            format = QgsRendererRangeLabelFormat()
            format.setFormat("%1 - %2")
            format.setPrecision(2)
            format.setTrimTrailingZeroes(True)

            symbol_style = QgsStyle().defaultStyle()
            color_ramp = symbol_style.colorRamp(ramp_name)
            color_ramp.invert()
            
            renderer = QgsGraduatedSymbolRenderer()
            renderer.setClassAttribute(value_field)
            renderer.setClassificationMethod(classification_method)
            renderer.setLabelFormat(format)
            renderer.updateClasses(layer, num_classes)
            renderer.updateColorRamp(color_ramp)
            renderer.updateSymbols(QgsMarkerSymbol.createSimple({'color': '#ff00ff', 'size': '2', 'outline_style': 'no'})) # color is irrelevant, "updateSymbols" will Update all the symbols but leave breaks and colors.  

            layer.setRenderer(renderer)
            layer.triggerRepaint()

            # Create plots (load from sqlite to pandas dataframe and then plot)
            try:
                cnx = sqlite3.connect(databasepath)
                df = pd.read_sql_query("SELECT * FROM trackpoints where {}".format(layer_filter), cnx)
                # find data to be plotted 
                df.select_dtypes(include='number').sum().loc[lambda x: x>0]
                sum_of_numeric_columns = df.select_dtypes(include='number').sum().loc[lambda x: x>0] #.sum returns a pd.series()
                plotable_columns = list(sum_of_numeric_columns[sum_of_numeric_columns>0].index) # extract indexes (i.e. column names)
                if 'distance' not in plotable_columns:
                    iface.messageBar().pushMessage("Info!", """There is no 'distance' field in your trackpoints data!""", level=Qgis.Info, duration=7)
                    return
                else:
                    relevant_plotable_columns = [col for col in plotable_columns if col not in ['start_time_utc','position_lat','position_lon','distance']]
                    relevant_plotable_columns.sort()
                    # create plots where we have some relevant data
                    fig, axes = plt.subplots(nrows=len(relevant_plotable_columns), ncols=1)
                    colors={'altitude':'k','cadence':'k','heartrate':'r','speed':'b','temperature':'g','vertical_speed':'c'}
                    #kinds={'altitude':'area','cadence':'scatter','heartrate':'line','speed':'line','temperature':'line','vertical_speed':'line'} # area is nice but then ymin = 0
                    kinds={'altitude':'line','cadence':'scatter','heartrate':'line','speed':'line','temperature':'line','vertical_speed':'line'}
                    
                    subplot_no = 0
                    for col in relevant_plotable_columns:
                        df.plot(ax=axes[subplot_no],x="distance", y=col, kind=kinds[col],style={col: colors[col],},alpha=0.5,grid=True)
                        subplot_no +=1
                    fig.suptitle('start time utc: {}'.format(start_time_utc.toString('yyyy-MM-dd hh:mm:ss')))
                    plt.show()
            except Exception as e:
                iface.messageBar().pushMessage("Error!", "Plotting failed due to error {}".format(e), level=Qgis.Critical, duration=7)
            
        else:
            iface.messageBar().pushMessage("Error!", "Select one feature in either 'sessions' or 'tracks' from your FIT-database (spatialite).", level=Qgis.Critical, duration=10)

    def help(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(__file__),'metadata.txt'))
        url = config.get('general', 'homepage')
        """open URL in web browser"""
        webbrowser.open(url)

