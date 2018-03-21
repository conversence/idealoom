"""RESTful API to assembl, with some magic.
It is guaranteed *NOT* to be stable, as it mirrors the model by introspection.
The basic URI to access any ressource is
GET ``/data/<Classname>/<instance db id>``
The ``local:`` uri prefix is meant to resolve to ``<http://servername/data/>``.

The other endpoints follow the pattern
``/data/<classname>/<instance id>(/<collection name>/<instance id>)+``
So we speak of class, instance or collection context, depending where we are in the URL.

It is generally possible to PUT or DEL on any instance context, 
and to POST to any class or collection context.
POST will return a 201 with the link in the body in the Location response header.

The set of collections available from an instance type is mostly given by the SQLAlchemy relations (and properties),
but there is a magic URL to obtain the list:
``/data/<classname>/<instance id>(/<collection name>/<instance id>)*/@@collections``

Another special case is when the collection name is actually a singleton.
In that case, one is allowed to use ``-`` instead of a database ID which one may not know.

A final special case is the collection ``/data/Discussion/<N>/all_users``, which has a shortcut to the logged-in user,
if any: ``/data/Discussion/<N>/all_users/current``

This module defines generic behaviour, but more specific views can be defined
through new view predicates: Look for ``add_view_predicate`` at the end of :py:mod:`assembl.views.traversal`, and there is an example in
the widget collection view in :py:mod:`assembl.views.api2.widget`.
Note that the view_config must have at least as many specifiers as the one it tries to override!

Permissions for the default views are specified by the crud_permissions class attribute, but more specific
views may have their own permissions system. 
For that reason, it will be generally useful to POST/PUT through collections accessed from the discussion, such as
``/data/Discussion/<number>(/<collection name>/<instance id>)+``
as opposed to the bare URLs ``/data/<Classname>/<instance db id>`` which are provided after a POST.
Traversing the discussion allows the user permissions specific to the discussion to be applied to the next operation.
The structure of those collection URLs will have to be reconstructed (from the POSTed collection, add the ID from the bare URL.)
"""

import os
import datetime
import inspect as pyinspect

from future.utils import string_types
from sqlalchemy import inspect
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPNotImplemented, HTTPUnauthorized, HTTPNotFound)
from pyramid.security import authenticated_userid, Everyone
from pyramid.response import Response
from pyramid.settings import asbool
from simplejson import dumps

from assembl.lib.sqla import ObjectNotUniqueError
from ..traversal import (
    InstanceContext, CollectionContext, ClassContext, Api2Context)
from assembl.auth import (
    P_READ, P_SYSADMIN, IF_OWNED, CrudPermissions)
from assembl.semantic.virtuoso_mapping import get_virtuoso
from assembl.models import (
    User, Discussion, TombstonableMixin)
from assembl.lib.decl_enums import DeclEnumType
from .. import JSONError

FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'js', 'tests', 'fixtures')
API_PREFIX = '/data/'

FORM_HEADER = "Content-Type:(application/x-www-form-urlencoded)|(multipart/form-data)"
JSON_HEADER = "Content-Type:application/(.*\+)?json"
MULTIPART_HEADER = "Content-Type:multipart/form-data"


def check_permissions(
        ctx, user_id, operation, cls=None):
    cls = cls or ctx.get_target_class()
    permissions = ctx.get_permissions()
    allowed = cls.user_can_cls(user_id, operation, permissions)
    if not allowed or (allowed == IF_OWNED and user_id == Everyone):
        raise HTTPUnauthorized()
    return allowed


class CreationResponse(Response):
    def __init__(
            self, ob_created, user_id=Everyone, permissions=(P_READ,),
            view='default', uri=None):
        uri = uri or ob_created.uri()
        super(CreationResponse, self).__init__(
            dumps(ob_created.generic_json(view, user_id, permissions)),
            location=uri, status_code=201, content_type="application/json",
            charset="utf-8")


@view_config(context=ClassContext, renderer='json',
             request_method='GET', permission=P_READ)
def class_view(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    check = check_permissions(ctx, user_id, CrudPermissions.READ)
    view = request.GET.get('view', None) or ctx.get_default_view() or 'id_only'
    tombstones = asbool(request.GET.get('tombstones', False))
    q = ctx.create_query(view == 'id_only', tombstones)
    if check == IF_OWNED:
        if user_id == Everyone:
            raise HTTPUnauthorized()
        q = ctx.get_target_class().restrict_to_owners(q, user_id)
    if view == 'id_only':
        return [ctx._class.uri_generic(x) for (x,) in q.all()]
    else:
        permissions = ctx.get_permissions()
        r = [i.generic_json(view, user_id, permissions) for i in q.all()]
        return [x for x in r if x is not None]


# @view_config(context=InstanceContext, renderer='json', name="jsonld",
#              request_method='GET', permission=P_READ,
#              accept="application/ld+json;q=0.9")
# @view_config(context=InstanceContext, renderer='json',
#              request_method='GET', permission=P_READ,
#              accept="application/ld+json;q=0.9")
def instance_view_jsonld(request):
    from assembl.semantic.virtuoso_mapping import AppQuadStorageManager
    from rdflib import URIRef, ConjunctiveGraph
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.READ, permissions):
        raise HTTPUnauthorized()
    discussion = ctx.get_instance_of_class(Discussion)
    if not discussion:
        raise HTTPNotFound()
    aqsm = AppQuadStorageManager()
    uri = URIRef(aqsm.local_uri() + instance.uri()[6:])
    d_storage_name = aqsm.discussion_storage_name(discussion.id)
    v = get_virtuoso(instance.db, d_storage_name)
    cg = ConjunctiveGraph(v, d_storage_name)
    result = cg.triples((uri, None, None))
    #result = v.query('select ?p ?o ?g where {graph ?g {<%s> ?p ?o}}' % uri)
    # Something is wrong here.
    triples = '\n'.join([
        '%s %s %s.' % (uri.n3(), p.n3(), o.n3())
        for (s, p, o) in result
        if '_with_no_name_entry' not in o])
    return aqsm.quads_to_jsonld(triples)


@view_config(context=InstanceContext, renderer='json',
             request_method='GET', accept="application/json")
def instance_view(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    request.logger().info('instance_view', instance=instance, _name='assembl.views.api2')
    if not instance.user_can(user_id, CrudPermissions.READ, permissions):
        raise HTTPUnauthorized()
    view = ctx.get_default_view() or 'default'
    view = request.GET.get('view', view)
    return instance.generic_json(view, user_id, permissions)


@view_config(context=CollectionContext, renderer='json',
             request_method='GET')
def collection_view(request, default_view='default'):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    check = check_permissions(ctx, user_id, CrudPermissions.READ)
    view = request.GET.get('view', None) or ctx.get_default_view() or default_view
    tombstones = asbool(request.GET.get('tombstones', False))
    q = ctx.create_query(view == 'id_only', tombstones)
    if check == IF_OWNED:
        if user_id == Everyone:
            raise HTTPUnauthorized()
        q = ctx.get_target_class().restrict_to_owners(q, user_id)
    if view == 'id_only':
        return [ctx.collection_class.uri_generic(x) for (x,) in q.all()]
    else:
        res = [i.generic_json(view, user_id, permissions) for i in q.all()]
        return [x for x in res if x is not None]


@view_config(context=InstanceContext, request_method='POST')
def instance_post(request):
    raise HTTPBadRequest()


@view_config(context=InstanceContext, request_method=('PATCH', 'PUT'), header=JSON_HEADER,
             renderer='json')
def instance_put_json(request, json_data=None):
    json_data = json_data or request.json_body
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.UPDATE, permissions):
        raise HTTPUnauthorized()
    try:
        updated = instance.update_from_json(json_data, user_id, ctx)
        view = request.GET.get('view', None) or 'default'
        if view == 'id_only':
            return [updated.uri()]
        else:
            return updated.generic_json(view, user_id, permissions)

    except NotImplementedError:
        raise HTTPNotImplemented()


def update_from_form(instance, form_data=None):
    mapper = inspect(instance.__class__)
    cols = {c.key: c for c in mapper.columns if not c.foreign_keys}
    setables = dict(pyinspect.getmembers(
        instance.__class__, lambda p:
        pyinspect.isdatadescriptor(p) and getattr(p, 'fset', None)))
    relns = {r.key: r for r in mapper.relationships if not r.uselist and
             len(r._calculated_foreign_keys) == 1 and iter(
                 r._calculated_foreign_keys).next().table == mapper.local_table
             }
    unknown = set(form_data.keys()) - (
        set(cols.keys()).union(set(setables.keys())).union(set(relns.keys())))
    if unknown:
        raise HTTPBadRequest("Unknown keys: "+",".join(unknown))
    params = dict(form_data)
    # type checking
    columns = {c.key: c for c in mapper.columns}
    for key, value in params.items():
        if key in relns and isinstance(value, string_types):
            val_inst = relns[key].class_.get_instance(value)
            if not val_inst:
                raise HTTPBadRequest("Unknown instance: "+value)
            params[key] = val_inst
        elif key in columns and isinstance(columns[key].type, DeclEnumType) \
                and isinstance(value, string_types):
            val_det = columns[key].type.enum.from_string(value)
            if not val_det:
                raise HTTPBadRequest("Cannot interpret " + value)
            params[key] = val_det
        elif key in columns and columns[key].type.python_type == datetime.datetime \
                and isinstance(value, string_types):
            val_dt = datetime.datetime.strpstr(value)
            if not val_dt:
                raise HTTPBadRequest("Cannot interpret " + value)
            params[key] = val_dt
        elif key in columns and columns[key].type.python_type == int \
                and isinstance(value, string_types):
            try:
                params[key] = int(value)
            except ValueError:
                raise HTTPBadRequest("Not a number: " + value)
        elif key in columns and not isinstance(value, columns[key].type.python_type):
            raise HTTPBadRequest("Value %s for key %s should be a %s" % (
                value, key, columns[key].type.python_type))
    try:
        for key, value in params.items():
            setattr(instance, key, value)
    except:
        raise HTTPBadRequest()


@view_config(context=InstanceContext, request_method='PUT', header=FORM_HEADER,
             renderer='json')
def instance_put_form(request, form_data=None):
    form_data = form_data or request.params
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.UPDATE, permissions):
        raise HTTPUnauthorized()
    update_from_form(instance, form_data)
    view = request.GET.get('view', None) or 'default'
    if view == 'id_only':
        return [instance.uri()]
    else:
        user_id = authenticated_userid(request) or Everyone
        return instance.generic_json(view, user_id, permissions)


@view_config(context=InstanceContext, request_method='DELETE', renderer='json')
def instance_del(request):
    ctx = request.context
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    instance = ctx._instance
    if not instance.user_can(user_id, CrudPermissions.DELETE, permissions):
        raise HTTPUnauthorized()
    if isinstance(instance, TombstonableMixin):
        instance.is_tombstone = True
    else:
        instance.db.delete(instance)
    # maybe instance.tombstone() ?
    return {}


@view_config(name="collections", context=InstanceContext, renderer='json',
             request_method="GET", permission=P_READ)
def show_collections(request):
    return request.context.get_collection_names()


@view_config(name="classes", context=Api2Context, renderer='json',
             request_method="GET", permission=P_READ)
def show_class_names(request):
    return request.context.all_class_names()


@view_config(context=CollectionContext, request_method='POST',
             header=JSON_HEADER)
def collection_add_json(request, json=None):
    ctx = request.context
    json = request.json_body if json is None else json
    user_id = authenticated_userid(request) or Everyone
    permissions = ctx.get_permissions()
    cls = ctx.get_collection_class(json.get('@type', None))
    typename = cls.external_typename()
    check_permissions(ctx, user_id, CrudPermissions.CREATE, cls)
    try:
        instances = ctx.create_object(typename, json)
    except Exception as e:
        raise HTTPBadRequest(e)
    if instances:
        first = instances[0]
        db = first.db
        for instance in instances:
            db.add(instance)
        db.flush()
        view = request.GET.get('view', None) or 'default'
        return CreationResponse(first, user_id, permissions, view)


def includeme(config):
    config.include('.discussion')
