import os, sys

from gi.repository import Gst, GES, GLib
Gst.init(None)
GES.init()

from gi.repository import GstPbutils

# The joys of globals, this needs to be done before
# importing Pipeline
if __name__=='__main__':
    from pitivi.check import check_requirements
    check_requirements()

from pitivi.utils.pipeline import Pipeline

here = os.path.abspath(os.path.dirname(__file__))

CLAP_ASSET = GLib.filename_to_uri(os.path.join(here, '15388__pitx__palma-08.wav'))

class ClapMixer(object):
    def __init__(self):
        self.__timeline = GES.Timeline.new()
        self.__timeline.add_track(GES.AudioTrack.new())
        self.pipeline = Pipeline()
        self.pipeline.set_timeline(self.__timeline)

        self.__clap_asset = None
        self.__clap_layer = None
        self.__asset_layer = None

        self.reset()

        GES.Asset.request_async(GES.UriClip, CLAP_ASSET,
                None, self.__clap_discovered_cb, None)

    def set_asset(self, asset):
        if self.__asset_layer is not None:
            self.__timeline.remove_layer(self.__asset_layer)

        if asset is None:
            return

        self.__asset_layer = self.__timeline.append_layer()
        self.__asset_layer.add_asset(asset, 0, 0, Gst.CLOCK_TIME_NONE,
                GES.TrackType.AUDIO)

        if self.pipeline.getState() in (Gst.State.PAUSED,
                Gst.State.PLAYING):
            self.pipeline.commit_timeline()

    def set_positions(self, positions):
       self.__positions = positions
       if self.__clap_asset:
           self.__setup_claps()

    def reset(self):
        self.pipeline.pause()
        # nle isn't thread-safe below PAUSED
        self.pipeline.get_state(timeout=Gst.CLOCK_TIME_NONE)

        self.pipeline.simple_seek(0)
        self.set_positions(None)
        self.set_asset(None)

    def __setup_claps(self):
        if self.__clap_layer is not None:
            self.__timeline.remove_layer(self.__clap_layer)
        self.__clap_layer = self.__timeline.append_layer()

        if self.__positions is None:
            return

        for position in self.__positions:
            self.__clap_layer.add_asset(self.__clap_asset,
                    position, 0, Gst.CLOCK_TIME_NONE, GES.TrackType.AUDIO)

        if self.pipeline.getState() in (Gst.State.PAUSED,
                Gst.State.PLAYING):
            self.pipeline.commit_timeline()

    def __clap_discovered_cb(self, asset, result, unused):
        self.__clap_asset = asset
        self.__setup_claps()


def change_positions(cm):
    cm.set_positions([t * Gst.SECOND for t in range(3,100)])
    return True

if __name__=='__main__':
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    check_requirements()
    cm = ClapMixer()
    asset = GES.UriClipAsset.request_sync(sys.argv[1])
    cm.set_asset(asset)
    loop = GLib.MainLoop()

    cm.pipeline.play()

    change, state, playing = cm.pipeline.get_state(timeout=Gst.CLOCK_TIME_NONE)

    cm.set_positions([t * Gst.SECOND for t in range(3,5)])

    GLib.timeout_add_seconds(1, change_positions, cm)

    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    cm.pipeline.set_state(Gst.State.NULL)
