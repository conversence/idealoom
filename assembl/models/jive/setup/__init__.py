from os import getcwd, mkdir
from os.path import exists, join
from shutil import copyfile, make_archive
from uuid import uuid4
from datetime import datetime
import pytz
import simplejson as json

from ....lib.config import get_config


bin_name = 'bin'
zip_name = 'assembl_jive_extension'
service_url_token = "%serviceURL%"

##
# The Un-RESTful verb used called by Jive to register add-on
jive_addon_registration_route = 'register_jive_addon'
jive_addon_unregistration_route = 'unregister_jive_addon'

##
# The Un-RESTful verb used by Assembl to create an add-on
jive_addon_creation = 'create_addon'

##
# The barebone for a meta.json file
# update the INSERT comments upon json creation
meta = {
    "package_version": "1.0",
    "id": "INSERT_UUID_HERE",
    "type": "client-app",
    "name": "Assembl OAuth Support",
    "description": "This add-on provides OAuth 2.0 support for the REST API",
    "minimum_version": "0070300000",
    "icon_16": "lightbulb-16.png",
    "icon_48": "lightbulb-48.png",
    "released_on": "2015-05-12T19:11:11.234Z",
    "register_url": "%serviceURL%/register",
    "unregister_url": "%serviceURL%/unregister",
    "service_url": "http://INSERT_URL_HERE"
}

##
# The barebone for the definition.json file
# Update this json according to ... in order to get more
# priviledges
definition = {
    "integrationUser": {
        "systemAdmin": "false",
    }
}


def create_meta_json(**kwargs):
    global meta
    now = datetime.utcnow()
    now.replace(tzinfo=pytz.utc)
    service_url = kwargs.get('service_url', 'http://localhost:6543')
    register_url = kwargs.get('register_url', "")
    unregister_url = kwargs.get('unregister_url', "")
    released_on = now.isoformat() + 'Z'  # Add UTC timezone
    uid = uuid4().__str__()

    meta.update({
        'released_on': released_on,
        'service_url': service_url,
        'register_url': register_url,
        'unregister_url': unregister_url,
        'id': uid
    })
    return meta


def create_definition_json(admin=False, **kwargs):
    global definition
    sysAdmin = admin
    definition.update({
        'integrationUser': {
            'systemAdmin': sysAdmin
        }
    })
    return definition


def write_json_to_file(data, path, name):
    if '.json' not in name:
        name = name + '.json'
    full_path = join(path, name)
    with open(full_path, 'w') as js:
        json.dump(data, js)


def compress(context):
    # in bin folder, make a new folder for the extension
    # make a data folder
    # make an i17n folder
    # make an extra folder
    # copy definition.json
    # copy meta.json
    # zip the new folder
    current_dir = getcwd()
    bin_dir = join(current_dir, bin_name)

    # first check in bin folder created. If not, create it
    if not exists(bin_dir):
        mkdir(bin_dir)

    now = datetime.utcnow()
    ext_name = 'assembl_jive_extension_' + now.strftime("%Y-%m-%d_%H-%M-%S")
    ext_dir = join(bin_dir, ext_name)
    mkdir(ext_dir)
    src_dir = join(ext_dir, 'src')
    mkdir(src_dir)
    mkdir(join(src_dir, 'data'))
    mkdir(join(src_dir, 'i18n'))
    mkdir(join(src_dir, 'extra'))

    config = get_config()
    write_json_to_file(
        create_meta_json(
            service_url=config.get('jive.service_url'),
            register_url=service_url_token + context + '/' + jive_addon_registration_route,
            unregister_url=service_url_token + context + '/' + jive_addon_unregistration_route
        ),
        src_dir,
        'meta.json'
    )

    write_json_to_file(
        create_definition_json(),
        src_dir,
        'definition.json'
    )

    copyfile(join(current_dir, "assembl/models/jive/setup/lightbulb-16.png"),
             join(src_dir, "data/lightbulb-16.png"))
    copyfile(join(current_dir, "assembl/models/jive/setup/lightbulb-48.png"),
             join(src_dir, "data/lightbulb-48.png"))

    make_archive(join(ext_dir, zip_name), 'zip', src_dir)
