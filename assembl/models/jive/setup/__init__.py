from os import getcwd, mkdir
from os.path import exists, join
from shutil import copyfile, make_archive
from uuid import uuid4
from datetime import datetime
from zipfile import ZipFile

import pytz
import simplejson as json


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
    uuid = kwargs.get('uuid')
    assert uuid
    released_on = now.isoformat() + 'Z'  # Add UTC timezone

    meta.update({
        'released_on': released_on,
        'service_url': service_url,
        'register_url': register_url,
        'unregister_url': unregister_url,
        'uuid': uuid
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


def create_jive_addon(source, dest_file):
    # in bin folder, make a new folder for the extension
    # make a data folder
    # make an i17n folder
    # make an extra folder
    # copy definition.json
    # copy meta.json
    # zip the new folder
    current_dir = getcwd()
    context = "%s/data/ContentSource/%d/" % (
        source.discussion.get_base_url(), source.id)
    zipfile = ZipFile(dest_file, 'w')
    zipfile.write(
        join(current_dir, "assembl/models/jive/setup/lightbulb-16.png"),
        "data/lightbulb-16.png")
    zipfile.write(
        join(current_dir, "assembl/models/jive/setup/lightbulb-48.png"),
        "data/lightbulb-48.png")

    source.addon_uuid = source.addon_uuid or str(uuid4())
    # TODO: add a column
    zipfile.writestr('meta.json', json.dumps(create_meta_json(
        register_url=context + jive_addon_registration_route,
        unregister_url=context + jive_addon_unregistration_route,
        uuid=source.addon_uuid
    )))
    zipfile.writestr('definition.json', json.dumps(create_definition_json()))
    zipfile.close()
