import os, threading
import pickle
import cairo

from gi.repository import Gtk, Gdk, GLib, Gst, GObject
from pyechonest import track as echotrack
from ordered_set import OrderedSet

from .clap_mixer import ClapMixer

from pitivi.extensions import BaseExtension
from pitivi.medialibrary import COL_URI
from pitivi.utils.misc import hash_file
from pitivi.settings import get_dir, xdg_cache_home

try:
    from pitivi.timeline import renderer
except ImportError:
    import renderer

here = os.path.abspath(os.path.dirname(__file__))

METADATA_BLACKLIST = ("pyechostring", "codestring", "synchstring",
        "analysis_url", "rhythmstring", "echoprintstring", "meta",
        "_object_type", "audio_md5", "cache", "code_version",
        "decoder_version", "echoprint_version", "id", "md5",
        "rhythm_version", "sample_md5", "status", "synch_version")

LIST_TYPED_METADATA = ("segments", "tatums", "beats", "bars", "sections")

class AudioPreviewer:
    def __init__(self, track, darea, clip_filename):
        filename = hash_file(clip_filename) + ".wave"
        cache_dir = get_dir(os.path.join(xdg_cache_home(), "waves"))
        filename = os.path.join(cache_dir, filename)

        self.darea = darea

        with open(filename, "rb") as samples:
            self.__peaks = pickle.load(samples)

        self.__nb_peaks = len(self.__peaks)
        self.__max_peak = max(self.__peaks)
        self.__track = track
        self.__surface = None
        self.__markers = []
        self.selected_section = None
        self.position = 0.0

        darea.connect('draw', self.draw_cb)

    def draw_cb(self, darea, context):
        rect = Gdk.cairo_get_clip_rectangle(context)
        clipped_rect = rect[1]
        width = int(darea.get_allocation().width)
        height = int(darea.get_allocation().height)

        playhead_index = int(self.position * self.__nb_peaks)

        self.__surface = renderer.fill_surface(self.__peaks[:],
                                             width,
                                             height,
                                             self.__max_peak,
                                             playhead_index)

        context.set_operator(cairo.OPERATOR_OVER)
        context.set_source_surface(self.__surface, 0, 0)

        context.paint()

        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_line_width(0.5)

        for marker in self.__markers:
            x = marker * width
            context.move_to(x, 0)
            context.line_to(x, height)

        context.stroke()

        context.set_source_rgb(1.0, 0.0, 0.0)
        context.set_line_width(0.5)

        x = self.position * width
        context.move_to(x, 0)
        context.line_to(x, height)

        context.stroke()

        if self.selected_section is not None:
            context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
            x1 = int(self.selected_section[0] * width)
            x2 = int(self.selected_section[1] * width)
            for x in range(x1, x2):
                context.move_to(x, 0)
                context.line_to(x, height)
                context.stroke()

    def set_markers(self, markers):
        self.__markers = markers

    def set_selected_section(self, startpos, endpos):
        self.selected_section = (startpos, endpos)

class EchonestExtension(BaseExtension):
    EXTENSION_NAME = 'echonest-extension'

    def __init__(self, app):
        BaseExtension.__init__(self, app)
        self.__asset_menu_item = None
        self.__analysis_handler_id = 0
        self.__audio_previewer = None
        self.__current_builder = None
        self.__clap_mixer = ClapMixer()
        self.__clap_mixer_handlers = []
        self.__current_track = None

        self.__button1_motion_start = None
        self.__button2_motion_end = None

        self.__selected_beats = None

    def setup(self):
        self.app.gui.medialibrary.connect('populating-asset-menu',
                self.__add_asset_menu_item_cb)
        self.app.gui.timeline_ui.timeline.connect('populating-clip-menu',
                self.__add_clip_menu_item_cb)

    def __load_from_cache(self, filename):
        filename = hash_file(filename) + '.analysis'
        cache_dir = get_dir(os.path.join(xdg_cache_home(), "echonest"))
        filename = os.path.join(cache_dir, filename)
        try:
            with open(filename, 'rb') as f:
                return pickle.load(f)
        except IOError:
            return None

    def __save_to_cache(self, filename, track):
        filename = hash_file(filename) + '.analysis'
        cache_dir = get_dir(os.path.join(xdg_cache_home(), "echonest"))
        filename = os.path.join(cache_dir, filename)
        with open(filename, 'wb') as f:
            pickle.dump(track, f)

    def analysis_worker(self, filename, callback, user_data):
        track = self.__load_from_cache(filename)

        if not track:
            track = echotrack.track_from_filename(filename)
            track.get_analysis()
            self.__save_to_cache(filename, track)

        if (callback):
            callback(track, *user_data)

    def __analyse_track(self, filename, callback, user_data):
        t = threading.Thread(target=self.analysis_worker, args=(filename,
            callback, user_data))
        t.daemon = True
        t.start()

    def __add_clip_menu_item_cb(self, timeline, clip, menu):
        menu_item = Gtk.MenuItem.new_with_label("Echonest dialog")
        menu_item.connect('activate',
                self.__clip_dialog_cb, clip)
        menu.append(menu_item)

    def __fill_metadata_list(self, track):
        listbox = self.__current_builder.get_object('metadata-list')
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

    def __prepare_beat_matcher(self, track, asset, filename):
        darea = self.__current_builder.get_object('waveform_area')
        self.__audio_previewer = AudioPreviewer(track, darea, filename)
        darea.get_style_context().add_class("AudioUriSource")

        for id_ in ('range-combo', 'select-type-combo', 'distribution-combo',
                'step-spinner'):
            self.__current_builder.get_object(id_).set_sensitive(True)

        self.__clap_mixer.set_asset(asset)
        self.__clap_mixer_handlers.append(
                self.__clap_mixer.pipeline.connect("state-change",
                self.__mixer_state_changed_cb))

        self.__clap_mixer.pipeline.activatePositionListener(50)
        self.__clap_mixer_handlers.append(self.__clap_mixer.pipeline.connect("position",
                self.__mixer_position_cb, track))

        step = int(self.__current_builder.get_object('step-spinner').get_value())
        self.__selected_beats = OrderedSet([b['start'] for b in track.beats[0::step]])

        self.__compute_markers()

    def __display_track_analysis(self, track, builder, asset, filename):
        if builder != self.__current_builder:
            return

        self.__current_track = track
        self.__fill_metadata_list(track)
        self.__prepare_beat_matcher(track, asset, filename)

    def __compute_markers(self):
        b = self.__current_builder
        t = self.__current_track
        claps = []

        range_ = b.get_object('range-combo').get_active_id()
        selection_type = b.get_object('select-type-combo').get_active_id()
        distribution = b.get_object('distribution-combo').get_active_id()
        step = int(b.get_object('step-spinner').get_value())

        if range_ == 'full':
            all_beats = [b['start'] for b in t.beats]
        elif self.__audio_previewer.selected_section:
            s = self.__audio_previewer.selected_section
            nb_beats = len(t.beats)
            start = int(s[0] * nb_beats)
            end = int(s[1] * nb_beats)
            all_beats = [b['start'] for b in t.beats[start:end]]
        else:
            all_beats = []

        selected_beats = all_beats[0::step]

        if selection_type == 'exactly':
            self.__selected_beats -= all_beats
            self.__selected_beats.update(selected_beats)
        elif selection_type == 'add':
            self.__selected_beats.update(selected_beats)
        else:
            self.__selected_beats -= selected_beats

        markers = [b / t.duration for b in self.__selected_beats]
        claps = [b * Gst.SECOND for b in self.__selected_beats]

        self.__clap_mixer.set_positions(claps)
        self.__audio_previewer.set_markers(markers)
        self.__audio_previewer.darea.queue_draw()

    def _match_spin_changed_cb(self, spinner):
        step = int(self.__current_builder.get_object('step-spinner').get_value())

        if step == 1:
            self.__current_builder.get_object('beat_label').set_text("beat")
        else:
            self.__current_builder.get_object('beat_label').set_text("beats")

    def _match_select_clicked_cb(self, unused_widget):
        self.__compute_markers()

    def _back_clicked_cb(self, unused_widget):
        self.__clap_mixer.pipeline.simple_seek(0)

    def _end_clicked_cb(self, unused_widget):
        #FIXME: do we even want that ?
        pass

    def _play_pause_clicked_cb(self, button):
        state = self.__clap_mixer.pipeline.getState()
        if state == Gst.State.PLAYING:
            self.__clap_mixer.pipeline.pause()
        else:
            self.__clap_mixer.pipeline.play()

    def _waveform_area_motion_notify_cb(self, darea, event):
        width = darea.get_allocation().width
        if self.__button1_motion_start is None:
            self.__button1_motion_start = event.x / width

        self.__button1_motion_end = event.x / width
        self.__select_waveform_section()

    def __select_waveform_section(self):
        startpos = max(0.0, min(self.__button1_motion_start,
            self.__button1_motion_end))
        endpos = min(1.0, max(self.__button1_motion_start,
            self.__button1_motion_end))
        self.__audio_previewer.set_selected_section(startpos, endpos)
        self.__audio_previewer.darea.queue_draw()

    def _waveform_area_button_release_cb(self, darea, event):
        position = event.x / darea.get_allocation().width

        if self.__button1_motion_start is None:
            nsposition = self.__current_track.duration * position * Gst.SECOND
            self.__clap_mixer.pipeline.simple_seek(int(nsposition))
        else:
            self.__select_waveform_section()

        self.__button1_motion_start = None
        self.__button1_motion_end = None

    def __clip_dialog_cb(self, widget, clip):
        clip = clip.bClip
        asset = clip.get_asset()
        filename = GLib.filename_from_uri(clip.props.uri)[0]

        self.__current_builder = Gtk.Builder()
        self.__current_builder.add_from_file(os.path.join(here, 'clip-dialog.ui'))
        self.__current_builder.connect_signals(self)
        self.__current_builder.get_object('step-spinner').set_range(1, 100)
        dialog = self.__current_builder.get_object('clip-dialog')
        dialog.set_transient_for(self.app.gui)

        self.__analyse_track(filename, self.__display_track_analysis,
                (self.__current_builder, asset, filename,))

        res = dialog.run()

        for handler_id in self.__clap_mixer_handlers:
            GObject.signal_handler_disconnect(self.__clap_mixer.pipeline,
                    handler_id)
        self.__clap_mixer_handlers = []

        self.__clap_mixer.reset()
        self.__current_builder = None
        self.__selected_beats = None

        # We gud
        dialog.destroy()

    def __add_asset_menu_item_cb(self, medialibrary, model_row, menu):
        menu_item = Gtk.MenuItem.new_with_label("Run echonest analysis")
        menu_item.connect('activate',
                self.__run_analysis_clicked_cb, model_row[COL_URI])
        menu.append(menu_item)

    def __run_analysis_clicked_cb(self, widget, asset_uri):
        self.__analyse_track(GLib.filename_from_uri(asset_uri)[0], None, None)

    def __mixer_state_changed_cb(self, unused_pipeline, new, prev):
        if not self.__current_builder:
            return

        image = self.__current_builder.get_object('play-pause-image')
        if new == Gst.State.PLAYING:
            image.set_from_icon_name('media-playback-pause', Gtk.IconSize.BUTTON)
        elif new == Gst.State.PAUSED:
            image.set_from_icon_name('media-playback-start', Gtk.IconSize.BUTTON)

    def __mixer_position_cb(self, unused_pipeline, position, track):
        if self.__audio_previewer:
            position_ratio = (position / Gst.SECOND) / track.duration
            self.__audio_previewer.position = position_ratio
            self.__audio_previewer.darea.queue_draw()

def get_extension_classes():
    return [EchonestExtension]
