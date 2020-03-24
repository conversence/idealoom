# -*- coding: utf-8 -*-
from __future__ import print_function
import os

from setuptools import setup, find_packages
from pip._internal.network.session import PipSession
from pip._internal.req import parse_requirements


HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.md')).read()
CHANGES = open(os.path.join(HERE, 'CHANGES.txt')).read()


def parse_reqs(*req_files):
    """returns a list of requirements from a list of req files"""
    requirements = set()
    session = PipSession()
    for req_file in req_files:
        # parse_requirements() returns generator of
        # pip.req.InstallRequirement objects
        parsed = parse_requirements(req_file, session=session)
        requirements.update({
            str(ir.req) for ir in parsed
            if (not ir.markers) or ir.markers.evaluate()})
    return list(requirements)


def widget_components():
    paths = []
    exclusions = {
        'browserify', 'jasmine', 'jsdoc', 'karma', 'mocha',
        'serve', 'src', '.sass-cache'}
    for (path, directories, filenames) in os.walk('assembl/static/widget'):
        if not set(path.split('/')).intersection(exclusions):
            paths.append(path)
    return [path[8:] + "/*" for path in paths]


setup(name='idealoom',
      version='0.1.0',
      description='Collective Intelligence platform',
      long_description=README + '\n\n' + CHANGES,
      long_description_content_type="text/markdown",
      classifiers=[
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Framework :: Pyramid",
          "Topic :: Communications",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Message Boards",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
          "License :: OSI Approved :: GNU Affero General Public License v3",
      ],
      author='Marc-Antoine Parent, Benoit Grégoire and others',
      author_email='maparent@conversence.com',
      url='https://idealoom.org/',
      project_urls={
          'Source': 'https://github.com/conversence/idealoom/',
          'Documentation': 'https://idealoom.org/techdocs/',
          'Gitter': 'https://gitter.im/conversence/idealoom',
      },
      license='AGPLv3',
      keywords='web wsgi pyramid',
      # find_packages misses alembic somehow.
      packages=find_packages() + [
          'assembl.alembic', 'assembl.alembic.versions'],
      package_data={
          'assembl': [
              'locale/*/LC_MESSAGES/*.json',
              'locale/*/LC_MESSAGES/*.mo',
              'static/js/build/*.js',
              'static/js/build/*.map',
              'static*/img/*',
              'static*/img/*/*',
              'static*/img/*/*/*',
              'static/css/fonts/*',
              'static/css/themes/default/*css',
              'static/css/themes/default/img/*',
              'static/js/app/utils/browser-detect.js',
              'static/js/bower/*/dist/css/*.css',
              'static/js/bower/*/dist/img/*',
              'static/js/bower/*/css/*.css',
              'static/js/bower/*/*.css',
              'view_def/*.json',
              'configs/*.rc',
              'configs/*.ini',
              'templates/*.jinja2',
              'templates/*/*.jinja2',
              'templates/*/*/*.jinja2',
              'templates/*/*.tmpl',
              'nlp/data/*',
              'nlp/data/stopwords/*',
              'semantic/ontology/*.ttl',
              'semantic/ontology/cache/*.ttl',
          ] + widget_components()
      },
      zip_safe=False,
      test_suite='assembl',
      setup_requires=['pip>=20'],
      install_requires=parse_reqs(
          'requirements.in', 'requirements_chrouter.in'),
      tests_require=parse_reqs('requirements_tests.in'),
      extras_require={
          'docs': parse_reqs('requirements_doc.in'),
          'dev': parse_reqs('requirements_dev.in'),
      },
      entry_points={
          "paste.app_factory": [
              "main = assembl:main",
              "maintenance = assembl.maintenance:main",
          ],
          "console_scripts": [
              "idealoom-db-manage = assembl.scripts.db_manage:main",
              "idealoom-ini-files = assembl.scripts.ini_files:main",
              "idealoom-imap-test = assembl.scripts.imap_test:main",
              "idealoom-add-user = assembl.scripts.add_user:main",
              "idealoom-pypsql = assembl.scripts.pypsql:main",
          ],
          'plaster.loader_factory': [
              'iloom+ini=assembl.lib.plaster:Loader',
              'iloom=assembl.lib.plaster:Loader',
          ],
          'plaster.wsgi_loader_factory': [
              'iloom+ini=assembl.lib.plaster:Loader',
              'iloom=assembl.lib.plaster:Loader',
          ],
      },
      )
