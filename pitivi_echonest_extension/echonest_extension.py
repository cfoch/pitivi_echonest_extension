import threading

from gi.repository import Gtk, GLib
from pyechonest import track

from pitivi.extensions import BaseExtension
from pitivi.medialibrary import COL_URI

class EchonestExtension(BaseExtension):
    EXTENSION_NAME = 'echonest-extension'

    def __init__(self, app):
        BaseExtension.__init__(self, app)
        self.__asset_menu_item = None
        self.__analysis_handler_id = 0

    def setup(self):
        self.app.gui.medialibrary.connect('populating-asset-menu',
                self.__add_asset_menu_item_cb)

    def analysis_worker(self, filename):
        pytrack = track.track_from_filename(filename)
        pytrack.get_analysis()
        print ("Found da track", dir(pytrack))

    def __analyse_track(self, filename):
        t = threading.Thread(target=self.analysis_worker, args=(filename,))
        t.daemon = True
        t.start()

    def __add_asset_menu_item_cb(self, medialibrary, model_row, menu):
        menu_item = Gtk.MenuItem.new_with_label("Run echonest analysis")
        menu_item.connect('activate',
                self.__run_analysis_clicked_cb, model_row[COL_URI])
        menu.append(menu_item)

    def __run_analysis_clicked_cb(self, widget, asset_uri):
        print ("I will now run analysis amigo", asset_uri)
        self.__analyse_track(GLib.filename_from_uri(asset_uri)[0])

def get_extension_classes():
    return [EchonestExtension]
