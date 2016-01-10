from pitivi.application import BaseExtension


class EchonestExtension(BaseExtension):
    EXTENSION_NAME = 'echonest-extension'

    def __init__(self, app):
        BaseExtension.__init__(self, app)

def get_extension_classes():
    return [EchonestExtension]
