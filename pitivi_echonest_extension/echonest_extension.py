import os, threading
import pickle
import cairo

from gi.repository import Gtk, Gdk, GLib
from pyechonest import track

from pitivi.extensions import BaseExtension
from pitivi.medialibrary import COL_URI
from pitivi.utils.misc import hash_file
from pitivi.settings import get_dir, xdg_cache_home

try:
    from pitivi.timeline import renderer
except ImportError:
    import renderer

print (renderer)

here = os.path.dirname(__file__)

METADATA_BLACKLIST = ("pyechostring", "codestring", "synchstring",
        "analysis_url", "rhythmstring", "echoprintstring", "meta",
        "_object_type", "audio_md5", "cache", "code_version",
        "decoder_version", "echoprint_version", "id", "md5",
        "rhythm_version", "sample_md5", "status", "synch_version")

LIST_TYPED_METADATA = ("segments", "tatums", "beats", "bars", "sections")

class AudioPreviewer:
    def __init__(self, darea, clip_filename):
        filename = hash_file(clip_filename) + ".wave"
        cache_dir = get_dir(os.path.join(xdg_cache_home(), "waves"))
        filename = os.path.join(cache_dir, filename)
        with open(filename, "rb") as samples:
            self.peaks = pickle.load(samples)

        self.__max_peak = max(self.peaks)

        self._surface_x = 0
        self.our_surface = None
        darea.connect('draw', self.draw_cb)

    def draw_cb(self, darea, context):
        rect = Gdk.cairo_get_clip_rectangle(context)
        clipped_rect = rect[1]

        self.our_surface = renderer.fill_surface(self.peaks[:],
                                             int(darea.get_allocation().width),
                                             int(darea.get_allocation().height),
                                             self.__max_peak)


        context.set_operator(cairo.OPERATOR_OVER)
        context.set_source_surface(self.our_surface, self._surface_x, 0)
        context.paint()

class EchonestExtension(BaseExtension):
    EXTENSION_NAME = 'echonest-extension'

    def __init__(self, app):
        BaseExtension.__init__(self, app)
        self.__asset_menu_item = None
        self.__analysis_handler_id = 0

        self.analysed_tracks = {}

    def setup(self):
        self.app.gui.medialibrary.connect('populating-asset-menu',
                self.__add_asset_menu_item_cb)
        self.app.gui.timeline_ui.timeline.connect('populating-clip-menu',
                self.__add_clip_menu_item_cb)

    def analysis_worker(self, filename):
        pytrack = track.track_from_filename(filename)
        pytrack.get_analysis()
        self.analysed_tracks[filename] = pytrack
        return pytrack

    def __analyse_track(self, filename):
        t = threading.Thread(target=self.analysis_worker, args=(filename,))
        t.daemon = True
        t.start()

    def __add_clip_menu_item_cb(self, timeline, clip, menu):
        menu_item = Gtk.MenuItem.new_with_label("Echonest dialog")
        menu_item.connect('activate',
                self.__clip_dialog_cb, clip)
        menu.append(menu_item)

    def __fill_metadata_list(self, builder, track):
        listbox = builder.get_object('metadata-list')
        for name, value in sorted(track.__dict__.items()):
            if name in METADATA_BLACKLIST:
                continue

            if name in LIST_TYPED_METADATA:
                text = "Number of %s : %d" % (name, len(value))
            else:
                text = "%s : %s" % (name, str(value))

            label = Gtk.Label.new(text)
            label.set_halign (Gtk.Align.START)

            if name in LIST_TYPED_METADATA:
                listbox.prepend(label)
            else:
                listbox.insert(label, -1)

        listbox.show_all()

    def __prepare_beat_matcher(self, builder, filename):
        darea = builder.get_object('waveform_area')
        self.audio_previewer = AudioPreviewer(darea, filename)
        darea.get_style_context().add_class("AudioUriSource")

    def __clip_dialog_cb(self, widget, clip):
        clip = clip.bClip
        filename = GLib.filename_from_uri(clip.props.uri)[0]
        track = self.analysed_tracks.get(filename)

        if not track:
            print ("Analysing sync")
            track = self.analysis_worker(filename)


        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(here, 'clip-dialog.ui'))
        builder.connect_signals(self)
        dialog = builder.get_object('clip-dialog')
        dialog.set_transient_for(self.app.gui)
        self.__fill_metadata_list(builder, track)
        self.__prepare_beat_matcher(builder, filename)
        res = dialog.run()

        # We gud
        dialog.destroy()

    def __add_asset_menu_item_cb(self, medialibrary, model_row, menu):
        menu_item = Gtk.MenuItem.new_with_label("Run echonest analysis")
        menu_item.connect('activate',
                self.__run_analysis_clicked_cb, model_row[COL_URI])
        menu.append(menu_item)

    def __run_analysis_clicked_cb(self, widget, asset_uri):
        self.__analyse_track(GLib.filename_from_uri(asset_uri)[0])

def get_extension_classes():
    return [EchonestExtension]
