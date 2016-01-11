from setuptools import setup, find_packages

setup(
    name = "pitivi_echonest_extension",
    version = "0.1",
    keywords = "pitivi echonest",
    url='https://github.com/pitivi/pitivi_echonest_extension',
    author_email = 'mathieu.duponchelle@opencreed.com',
    license = 'LGPL',
    description = "An extension for pitivi that integrates the echonest API",
    author = "Mathieu Duponchelle",
    packages = find_packages(),

    entry_points = {'pitivi.extensions': 'get_extension_classes = pitivi_echonest_extension.echonest_extension:get_extension_classes'},
    install_requires = [
    ],
)
