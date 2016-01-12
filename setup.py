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
    package_data = {
        '': ['*.ui'],
    },
    dependency_links = \
            ['http://github.com/LuminosoInsight/ordered-set/tarball/master#egg=ordered_set-2.0.0',
             'http://github.com/MathieuDuponchelle/pyechonest3/tarball/py3#egg=pyechonest-9.0.3'],
    install_requires = [
        "ordered-set==2.0.0",
        "pyechonest==9.0.3",
    ],
)
