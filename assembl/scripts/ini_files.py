#!/usr/bin/env python
""" Generate various secondary INI files from the main INI file. """
from __future__ import print_function

from future import standard_library
standard_library.install_aliases()
standard_library.install_hooks()
from future.utils import bytes_to_native_str

import sys
import os
import io
from os.path import exists, dirname, abspath, join, realpath
from configparser import (NoSectionError, NoOptionError, ConfigParser)
from argparse import ArgumentParser, FileType
import logging
from future.utils import string_types
import locale

from ..fabfile import combine_rc, code_root, venv_path, filter_global_names, fill_template


if sys.platform == 'darwin':
    locale.setlocale(locale.LC_CTYPE, "UTF-8")
else:
    locale.setlocale(locale.LC_CTYPE, "C.UTF-8")

log = logging.getLogger('assembl')
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

# Case sensitive options
ConfigParser.optionxform = lambda self, option: option


local_code_root = dirname(dirname(realpath(__file__)))

SECTION = 'app:idealoom'
RANDOM_FILE = 'random.ini'

# The defaults allow to set sensible values and not edit all the local.ini
# files. Err towards conservative production values.
# If something SHOULD be defined, assert its presence later on.
# TODO: Subclass ConfigParser to give a warning whenever a value
# is taken from the defaults.

# TODO: check encoding?

DEFAULTS = {
    # Define either the first or all others.
    'celery_tasks.broker': '',
    'celery_tasks.imap.broker': '',
    'celery_tasks.notification_dispatch.broker': '',
    'celery_tasks.notify.broker': '',
    'celery_tasks.translate.broker': '',
    # num_workers: These are production values
    'celery_tasks.imap.num_workers': '1',
    'celery_tasks.notification_dispatch.num_workers': '1',
    'celery_tasks.notify.num_workers': '2',
    'celery_tasks.translate.num_workers': '2',
    # Sensible defaults
    'autostart_celery': 'true',
    'autostart_celery_notify_beat': 'true',
    'autostart_source_reader': 'true',
    'autostart_changes_router': 'true',
    'autostart_pserve': 'false',
    'autostart_webpack': 'false',
    'autostart_uwsgi': 'false',
    'autostart_metrics_server': 'false',
    'autostart_edgesense_server': 'false',
    'circus_log_size': '1048576',  # ~1Mb
    'circus_log_backups': '3',
    'instance_name': 'idealoom',
}


def find_ini_file(fname, *locs):
    if exists(fname):
        return fname
    locs = list(locs)
    locs.append(join(local_code_root, 'configs'))
    for loc in locs:
        name = join(loc, fname)
        if exists(name):
            return name


def asParser(fob, interpolation=None):
    """ConfigParser from a .ini filename or open file object. Idempotent."""
    if isinstance(fob, ConfigParser):
        return fob
    if interpolation is True:
        parser = ConfigParser()
    else:
        parser = ConfigParser(interpolation=interpolation)
    if isinstance(fob, string_types):
        fob2 = find_ini_file(fob)
        assert fob2, "Cannot find " + fob
        parser.read(fob2)
    else:
        parser.readfp(fob)
    return parser


def ensureSection(config, section):
    """Ensure that config has that section"""
    if section.lower() != 'default' and not config.has_section(section):
        config.add_section(section)


def generate_ini_files(config, config_fname):
    """Generate the circusd.conf from its template and .ini file."""
    # TODO: Use .rc file instead of .ini file.
    def get_default(key, default=None, section=SECTION):
        if config.has_option(section, key):
            return config.get(section, key)
        return default

    try:
        metrics_code_dir = config.get('metrics', 'metrics_code_dir')
        metrics_cl = config.get('metrics', 'metrics_cl')
        has_metrics_server = (
            metrics_code_dir and exists(metrics_code_dir) and
            exists(metrics_cl.split()[0]))
    except NoSectionError:
        has_metrics_server = False
        metrics_cl = '/bin/ls'  # innocuous
        metrics_code_dir = ''
    try:
        edgesense_code_dir = config.get('edgesense', 'edgesense_code_dir')
        edgesense_venv = config.get('edgesense', 'venv')
        has_edgesense_server = (
            edgesense_code_dir and exists(edgesense_code_dir) and
            exists(join(
                edgesense_venv, 'bin', 'edgesense_catalyst_server')))
        edgesense_venv_directive = 'virtualenv = '+edgesense_venv
    except NoSectionError:
        has_edgesense_server = False
        edgesense_venv = '/tmp'  # innocuous
        edgesense_code_dir = ''
    if not has_edgesense_server:
        edgesense_venv_directive = ''
    celery_broker = config.get(
        SECTION, 'celery_tasks.broker')
    secure = config.getboolean(SECTION, 'require_secure_connection')
    public_hostname = config.get(SECTION, 'public_hostname')
    url = "http%s://%s" % ('s' if secure else '', public_hostname)
    port = config.getint(SECTION, 'public_port')
    # default_port = 443 if secure else 80
    # if port != default_port:
    if port not in (80, 443):
        url += ':' + str(port)
    if secure and port == 80:
        # old misconfiguration
        port = 443
    webpack_port = int(get_default('webpack_port', 8080))
    webpack_host = get_default('webpack_host', public_hostname)
    webpack_url = "http://%s:%d" % (webpack_host, webpack_port)
    here = dirname(abspath('circusd.conf'))
    log_dir = join(here, 'var', 'log')
    vars = {
        'CELERY_BROKER': celery_broker,
        'CELERY_NUM_WORKERS': config.get(
            SECTION, 'celery_tasks.num_workers'),
        'instance_name': config.get(SECTION, 'instance_name'),
        'here': here,
        'log_dir': log_dir,
        'CONFIG_FILE': config_fname,
        'metrics_code_dir': metrics_code_dir,
        'metrics_cl': metrics_cl,
        'circus_statsd': config.get('circus', 'use_statsd'),
        'circus_webapp': config.get('circus', 'use_webapp'),
        'lcctype': config.get(SECTION, 'lcctype'),
        'circus_webapp_port': int(config.get('circus', 'webapp_port')),
        'chaussette_port': int(config.get('circus', 'chaussette_port')),
        'edgesense_venv': edgesense_venv_directive,
        'VIRTUAL_ENV': os.environ['VIRTUAL_ENV'],
        'edgesense_code_dir': edgesense_code_dir,
        'WEBPACK_URL': webpack_url,
        'server_port': config.getint('server:main', 'port'),
        'ASSEMBL_URL': url,
        'code_root': config.get(SECTION, 'code_root'),
    }
    for procname in (
            'celery',
            'celery_notify_beat',
            'source_reader',
            'changes_router',
            'pserve',
            'webpack',
            'chaussette',
            'maintenance',
            'metrics',
            'metrics_py',
            # 'edgesense',
            'uwsgi'):
        name = 'autostart_' + procname
        if procname == 'metrics_py':
            name = 'autostart_metrics'
        autostart = config.get('circus', name)
        if procname == 'edgesense':
            autostart = autostart and has_edgesense_server
        elif procname == 'metrics':
            autostart = autostart and has_metrics_server
        vars[name] = autostart
        for component in ('size', 'backups'):
            for stream in ('err', 'out'):
                name0 = 'circus_log_' + component
                name1 = '_'.join((name0, procname))
                name = '_'.join((name1, stream))
                try:
                    val = config.get('circus', name)
                except NoOptionError:
                    try:
                        val = config.get('circus', name1)
                    except NoOptionError:
                        # Fallbacks to value from DEFAULTS
                        val = config.get('circus', name0)
                vars[name] = val

    for fname in ('circusd.conf',):
        templateloc = join(local_code_root, 'templates', 'system', fname + '.tmpl')
        with open(templateloc) as tmpl, open(fname, 'w') as inifile:
            inifile.write(tmpl.read() % vars)
        print(fname)


def combine_ini(config, overlay, adding=True):
    """Overlay values of the second ini file on the first.

    Returns a ConfigParser object
    If adding is false, only existing values will be replaced.
    """
    config = asParser(config)
    overlay = asParser(overlay)
    for section in overlay.sections():
        # Avoid including DEFAULTSECT
        for key in overlay._sections[section]:
            value = overlay.get(section, key)
            if adding or config.has_option(section, key):
                ensureSection(config, section)
                config.set(section, key, value)
    if overlay._defaults:
        config._defaults.update(overlay._defaults)
    return config


def migrate_beaker_config(random_ini, overlay):
    """Migrate old-style session... to beaker.session..."""
    PREFIX = "beaker."
    for section in random_ini.sections():
        # Avoid including DEFAULTSECT
        if not overlay.has_section(section):
            continue
        o_section = overlay._sections[section]
        for key in random_ini._sections[section]:
            if key.startswith(PREFIX):
                old_key = key[len(PREFIX):]
                if old_key in o_section and key not in o_section:
                    overlay.set(section, key, overlay.get(section, old_key))
            elif key == 'session.secret':
                alt_key = 'beaker.' + key
                if alt_key in o_section and key not in o_section:
                    overlay.set(section, key, overlay.get(section, alt_key))
    return overlay


def dump(ini_file):
    """Dump the ini file, showing interpolations and errors."""
    ini_file = asParser(ini_file, True)
    ini_file._defaults['here'] = os.getcwd()
    for section in ini_file.sections():
        print("\n[%s]\n" % section)
        for option in ini_file._sections[section]:
            print(option, '=', end=' ')
            try:
                print(ini_file.get(section, option))
            except Exception as e:
                print(ini_file.get(section, option, True))
                print("*"*15, "Could not interpolate")
                print(e)


def populate_random(random_file, random_templates=None, saml_info=None):
    """Populate random.ini

    Create missing random values according to the template
    Do not change existing values"""
    from base64 import b64encode
    from os import urandom
    from assembl.auth.make_saml import (
        make_saml_key, make_saml_cert, cleanup_x509_text)
    base = ConfigParser(interpolation=None)
    assert random_templates, "Please give one or more templates"
    for template in random_templates:
        if (not exists(template)):
            template = join(local_code_root, 'templates', 'system', template)
        assert exists(template), "Cannot find template " + template
        base.read(template)
    existing = ConfigParser(interpolation=None)
    if exists(random_file):
        existing.read(random_file)
    combine_ini(base, existing)
    saml_keys = {}
    changed = False

    for section in base.sections():
        for key, value in base.items(section):
            keyu = key.upper()
            # too much knowdledge, but hard to avoid
            if "SAML" in keyu and keyu.endswith("_PRIVATE_KEY"):
                prefix = keyu[:-12]
                if value == "{saml_key}":
                    saml_key_text, saml_key = make_saml_key()
                    saml_key_text = cleanup_x509_text(saml_key_text)
                    base.set(section, key, saml_key_text)
                    saml_keys[prefix] = saml_key
                    changed = True
                else:
                    saml_keys[prefix] = value
            elif value.startswith('{random') and value.endswith("}"):
                size = int(value[7:-1])
                assert 0 < size < 100
                value = bytes_to_native_str(b64encode(urandom(size)))
                base.set(section, key, value)
                changed = True

    # Do certs in second pass, to be sure keys are set
    for section in base.sections():
        for key, value in base.items(section):
            keyu = key.upper()
            if ("SAML" in keyu and keyu.endswith("_PUBLIC_CERT") and
                    value == '{saml_cert}'):
                assert saml_info
                prefix = keyu[:-12]
                # If key is not there, it IS a mismatch and and error.
                saml_key = saml_keys[prefix]
                saml_cert_text, _ = make_saml_cert(saml_key, **saml_info)
                saml_cert_text = cleanup_x509_text(saml_cert_text)
                base.set(section, key, saml_cert_text)
                changed = True
    if changed:
        with open(random_file, 'w') as f:
            base.write(f)
    return base


def rc_to_ini(rc_info, default_section=SECTION):
    """Convert a .rc file to a ConfigParser (.ini-like object)

    Items are assumed to be in app:idealoom section,
        unless prefixed by "{section}__" .
    Keys prefixed with an underscore are not passed on.
    Keys prefixed with a star are put in the global (DEFAULT) section.
    Value of '__delete_key__' is eliminated if existing.
    """
    p = ConfigParser(interpolation=None)
    for key, val in rc_info.items():
        if not key or key.startswith('_') or key is 'hosts':
            continue
        if key[0] == '*':
            # Global keys
            section = "DEFAULT"
            key = key[1:]
        elif '__' in key:
            section, key = key.split('__', 1)
        else:
            section = default_section
        ensureSection(p, section)
        if val == '__delete_key__':
            # Allow to remove a variable from rc
            # so we can fall back to underlying ini
            p.remove_option(section, key)
        else:
            p.set(section, key, val)
    return p


def iniconfig_to_rc(parser, dest=None, extends=None, target_dir=None):
    """Convert a ConfigParser to a .rc file.

    That file is written to dest, or to a returned file-like object
    extends specifies an extended ini file."""
    from io import StringIO
    if dest is None:
        dest = StringIO()
    if extends:
        if target_dir is not None:
            target_dir = os.path.abspath(target_dir)
            extends_dir = os.path.abspath(os.path.dirname(extends))
            extends = os.path.join(os.path.relpath(extends_dir, target_dir),
                                   os.path.basename(extends))
        dest.write("_extends = %s\n" % (extends,))
    for section in parser.sections():
        if section == SECTION:
            prefix = ''
        else:
            prefix = section + '__'
        for key, value in parser.items(section):
            if '\n' in value:
                log.warning("avoid multiline values in RC: %s=%s" % (key, value))
                value = ' '.join(value.split('\n'))
            dest.write("%s%s = %s\n" % (prefix, key, value))
    if hasattr(dest, 'seek'):
        dest.seek(0)
    return dest


def extract_saml_info(rc_info):
    """Extract SAML variables from the state"""
    saml_info = {k[5:]: v for (k, v) in rc_info.items()
                 if k.startswith('saml_')}
    saml_info['domain'] = rc_info['public_hostname']
    return saml_info


def diff_ini(first, second, diff=None, existing_only=False):
    """Diff ini files

    Generate a parser with any value in the second that is different in the first.
    Returns a ConfigParser.
    Takes interpolation into account. Does not include values that disappeared."""
    from configparser import _Chainmap
    first = asParser(first)
    second = asParser(second)
    # TODO: Look at first both in raw and formatted versions
    diff = diff or ConfigParser(interpolation=None)
    interpolating = ConfigParser()
    for section in second.sections():
        if section != 'DEFAULT' and not first.has_section(section):
            if not existing_only:
                diff.add_section(section)
                for option in second.options(section):
                    value = second.get(section, option)
                    diff.set(section, option, value)
        else:
            vars = _Chainmap(second._sections[section], first._sections[section], second._defaults, first._defaults)
            for option, value2 in second.items(section):
                if not first.has_option(section, option):
                    if not existing_only:
                        ensureSection(diff, section)
                        diff.set(section, option, value2)
                    continue
                value1 = first.get(section, option)
                if value1 != value2 and '%(' in value1:
                    # try to interpolate, and see if it would amount to the same.
                    try:
                        value1 = interpolating._interpolate(section, option, value1, vars)
                    except Exception as e:
                        pass
                if value1 != value2:
                    ensureSection(diff, section)
                    diff.set(section, option, value2)
    return diff


def compose(rc_filename, random_file=None):
    """Compose local.ini from the given .rc file"""
    rc_info = combine_rc(rc_filename)
    rc_info['*code_root'] = code_root(rc_info)
    # Special case: uwsgi does not do internal computations.
    rc_info['uwsgi__virtualenv'] = venv_path(rc_info)
    ini_sequence = rc_info.get('ini_files', None)
    assert ini_sequence, "Define ini_files"
    ini_sequence = ini_sequence.split()
    base = ConfigParser(interpolation=None)
    random_file = random_file or rc_info.get('random_file', RANDOM_FILE)
    for overlay in ini_sequence:
        if overlay == 'RC_DATA':
            overlay = rc_to_ini(rc_info)
        elif overlay.startswith('RANDOM'):
            templates = overlay.split(':')[1:]
            overlay = populate_random(
                random_file, templates, extract_saml_info(rc_info))
        else:
            overlay = find_ini_file(overlay, dirname(rc_filename))
            assert overlay, "Cannot find " + overlay
        combine_ini(base, overlay)
    return base


def extract_random_templates(ini_files):
    ini_files = ini_files or ''
    random = [f for f in ini_files.split() if f.startswith("RANDOM")]
    if random:
        assert len(random) == 1, "Only a single random element in ini_files"
        return random[0].split(":")[1:]
    return []


def migrate(rc_filename, expected_ini, random_file=None, target_dir=None):
    """Create a overlay.rc file from the local.ini and a base .rc file"""
    expected_ini = asParser(expected_ini)
    rc_data = combine_rc(rc_filename)
    ini_files = rc_data.get('ini_files', None)
    random_file = random_file or rc_data.get('random_file', RANDOM_FILE)
    templates = extract_random_templates(ini_files)
    if templates:
        random_data = populate_random(
            random_file, templates, extract_saml_info(rc_data))
        migrate_beaker_config(random_data, expected_ini)
        random_data = combine_ini(random_data, expected_ini, False)
        with open(random_file, 'w') as f:
            random_data.write(f)
    else:
        random_file = None
    base = compose(rc_filename, random_file)
    diff = diff_ini(base, expected_ini)
    return iniconfig_to_rc(diff, extends=rc_filename, target_dir=target_dir)


def write_parser(parser, dest=None):
    if dest is None:
        parser.write(sys.stdout)
    else:
        with io.open(dest, 'w', encoding='utf-8') as destf:
            parser.write(destf)


def main():
    parser = ArgumentParser(prog=os.path.basename(__file__))
    subparsers = parser.add_subparsers(dest='command', title="subcommands")

    def short_help(fn):
        return fn.__doc__.split('\n')[0]

    # ini populate
    parser_populate = subparsers.add_parser(
        'populate', help=short_help(generate_ini_files))
    parser_populate.add_argument(
        'config',
        help='The source ini file')

    # ini combine
    parser_combine = subparsers.add_parser(
        'combine', help=short_help(combine_ini))
    parser_combine.add_argument('--output', '-o', default=None,
                                help='The output file')
    parser_combine.add_argument('input', type=FileType('r'), nargs='+',
                                help='Input ini files')

    # ini compose
    parser_compose = subparsers.add_parser('compose', help=short_help(compose))
    parser_compose.add_argument('--output', '-o', default=None,
                                help='The output file')
    parser_compose.add_argument('--random', '-r', help='random.ini file',
                                default=None)
    parser_compose.add_argument('input', help='Input rc file')

    # ini migrate
    parser_migrate = subparsers.add_parser(
        'migrate', help=short_help(migrate))
    parser_migrate.add_argument('--output', '-o', default=None,
                                help='The output file')
    parser_migrate.add_argument(
        '--ini', '-i', type=FileType('r'), default=None,
        help="INI file we're migrating, usually local.ini")
    parser_migrate.add_argument('--random', '-r', default=None,
                                help='file where random values will be stored,'
                                     ' and fetched if existing',)
    parser_migrate.add_argument('rc', help='Base rc file')

    # random.ini
    parser_random = subparsers.add_parser(
        'random', help=short_help(populate_random))
    parser_random.add_argument('--random', '-r', help='random.ini file',
                               default=None)
    parser_random.add_argument('--output', '-o', default=None,
                               help='The output file')
    parser_random.add_argument('--template', '-t', help='random template files',
                               action='append', default=[])
    parser_random.add_argument('input', help='Input rc file (for saml)')

    # dump .ini
    parser_dump = subparsers.add_parser(
        'dump', help=short_help(dump))
    parser_dump.add_argument('ini', help='Input ini file')

    # ini diff
    parser_diff = subparsers.add_parser('diff', help=short_help(diff_ini))
    parser_diff.add_argument('--output', '-o', default=None,
                             help='The output file')
    parser_diff.add_argument(
        '--existing_only', '-e', action="store_true", default=False,
        help='Only show changes to keys existing in first file')
    parser_diff.add_argument('base', type=FileType('r'),
                             help='Base ini file')
    parser_diff.add_argument('second', type=FileType('r'),
                             help='Second ini file')

    # template from rc file
    parser_random = subparsers.add_parser(
        'template', help=short_help(populate_random))
    parser_random.add_argument('--output', '-o', type=FileType('w'),
                               default=sys.stdout, help='The output file')
    parser_random.add_argument('input', help='Input rc file')
    parser_random.add_argument('template', help='template file (python or jinja2)')

    args = parser.parse_args()
    if args.command == 'populate':
        config = ConfigParser(defaults=DEFAULTS)
        config.read(args.config)
        generate_ini_files(config, args.config)
    elif args.command == 'combine':
        base = asParser(args.input[0])
        for overlay in args.input[1:]:
            combine_ini(base, overlay)
        write_parser(base, args.output)
    elif args.command == 'random':
        rc_info = combine_rc(args.input)
        random_file = args.random or rc_info.get('random_file', RANDOM_FILE)
        templates = args.template or extract_random_templates(
            rc_info.get('ini_files', ''))
        random = populate_random(
            random_file, templates, extract_saml_info(rc_info))
        write_parser(random, args.output)
    elif args.command == 'compose':
        ini_info = compose(args.input, args.random)
        write_parser(ini_info, args.output)
    elif args.command == 'migrate':
        ini_file = args.ini
        if ini_file is None:
            ini_file = asParser('local.ini')
        else:
            ini_file = asParser(ini_file)

        target_dir = os.path.dirname(args.output) if args.output else None
        rc_file = migrate(args.rc, ini_file, args.random, target_dir=target_dir)
        if args.output:
            with io.open(args.output, 'w', encoding='utf-8') as output:
                output.write(rc_file.getvalue())
        else:
            sys.stdout.write(rc_file.getvalue())
    elif args.command == 'diff':
        diff = diff_ini(args.base, args.second,
                        existing_only=args.existing_only)
        write_parser(diff, args.output)
    if args.command == 'dump':
        dump(args.ini)
    if args.command == 'template':
        rc_info = filter_global_names(combine_rc(args.input))
        fill_template(args.template, rc_info, args.output)


if __name__ == '__main__':
    main()
