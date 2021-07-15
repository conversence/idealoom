#!/usr/bin/env python
"""Clone a discussion, either within or between databases."""
from __future__ import print_function

# Put something like this in the crontab:
# 10 3 * * * cd /var/www/assembl ; ./venv/bin/python assembl/scripts/clone_discussion.py -n assembldemosandbox -d -p system.Authenticated+admin_discussion -p system.Authenticated+add_post -p system.Authenticated+add_extract -p system.Authenticated+edit_extract -p system.Authenticated+add_idea -p system.Authenticated+edit_idea -p system.Authenticated+edit_synthesis -p system.Authenticated+vote -p system.Authenticated+read local.ini assembldemo

from builtins import next
from builtins import str
import itertools
from collections import defaultdict
import argparse
from inspect import isabstract, signature, isclass
import logging.config
import traceback
from functools import partial
import pdb
from os.path import abspath

from pyramid.paster import get_appsettings, bootstrap
from sqlalchemy.orm import (
    class_mapper, undefer, with_polymorphic, sessionmaker)
from sqlalchemy.orm.properties import ColumnProperty
import transaction
from sqlalchemy.sql.visitors import ClauseVisitor
from sqlalchemy.sql.expression import and_
from sqlalchemy import inspect

from assembl.auth import SYSTEM_ROLES, ASSEMBL_PERMISSIONS
from assembl.lib.config import set_config, get_config
from assembl.lib.sqla import (
    configure_engine, get_session_maker, make_session_maker, get_metadata,
    session_maker_is_initialized)
from assembl.lib.zmqlib import configure_zmq
from assembl.lib.model_watcher import configure_model_watcher
from assembl.lib.raven_client import setup_raven, capture_exception


def find_or_create_object_by_keys(db, keys, obj, columns=None, joins=None):
    args = {key: getattr(obj, key) for key in keys}
    eq = db.query(obj.__class__).filter_by(**args)
    if joins:
        for rel_name in joins:
            joined_obj = getattr(obj, rel_name)
            assert joined_obj
            corresponding = find_or_create_object(joined_obj)
            assert corresponding
            eq = eq.filter_by(rel_name=corresponding)
            args[rel_name] = corresponding
    eq = eq.first()
    if eq is None:
        if columns is not None:
            args.update({key: getattr(obj, key) for key in columns})
        if "session" in signature(obj.__class__.__init__).parameters:
            args["session"] = db
        eq = obj.__class__(**args)
        db.add(eq)
    return eq


fn_for_classes = None

user_refs = None

special_extra_tests = None


def init_key_for_classes(db):
    global fn_for_classes, user_refs, special_extra_tests
    from assembl.models import (
        AgentProfile, User, Permission, Role, Webpage, Action, LocalUserRole,
        IdentityProvider, EmailAccount, WebLinkAccount, Preferences, URIRefDb,
        NotificationSubscription, DiscussionPerUserNamespacedKeyValue,
        IdeaLocalUserRole, PublicationFlow, PublicationState,
        PublicationTransition, MultiCriterionVotingWidget)
    fn_for_classes = {
        AgentProfile: partial(find_or_create_agent_profile, db),
        User: partial(find_or_create_agent_profile, db),
        URIRefDb: partial(find_or_create_urlref, db),
        Webpage: partial(find_or_create_object_by_keys, db, ['url']),
        Permission: partial(find_or_create_object_by_keys, db, ['name']),
        Preferences: partial(find_or_create_object_by_keys, db, ['name']),
        Role: partial(find_or_create_object_by_keys, db, ['name']),
        PublicationFlow: partial(find_or_create_object_by_keys, db, ['name']),
        PublicationState: partial(find_or_create_object_by_keys, db, ['name'], joins=['flow']),
        PublicationTransition: partial(find_or_create_object_by_keys, db, ['name'], joins=['flow']),
        # SocialAuthAccount: partial(find_or_create_object_by_keys, db, ['provider_id', 'uid']),
        IdentityProvider: partial(find_or_create_object_by_keys, db, ['provider_type', 'name']),
        # email_ci?
        EmailAccount: partial(find_or_create_object_by_keys, db, ['email'], columns=['preferred']),
        WebLinkAccount: partial(find_or_create_object_by_keys, db, ['user_link']),
    }
    # these are objects that refer to users and should not be copied
    user_refs = {
        Action: 'actor',
        NotificationSubscription: 'user',
        LocalUserRole: 'user',
        IdeaLocalUserRole: 'user',
        DiscussionPerUserNamespacedKeyValue: 'user',
    }
    special_extra_tests = {
        Preferences: lambda ob: ob.name == Preferences.BASE_PREFS_NAME
    }


def find_or_create_object(ob):
    global fn_for_classes
    assert ob.__class__ in fn_for_classes
    return fn_for_classes[ob.__class__](ob)


def is_special_class(ob):
    global fn_for_classes, special_extra_tests
    if ob.__class__ in fn_for_classes:
        if ob.__class__ in special_extra_tests:
            return special_extra_tests[ob.__class__](ob)
        return True
    if ob.__class__.__name__ == 'UserTemplate':
        return False
    assert not isinstance(ob, tuple(fn_for_classes.keys())),\
        "Missing subclass: " + ob.__class__
    return False


def find_or_create_provider_account(db, account):
    from assembl.models import SocialAuthAccount
    assert isinstance(account, SocialAuthAccount)
    # Note: need a similar one for SourceSpecificAccount
    identity_provider = find_or_create_object(account.identity_provider)
    args = {
        "identity_provider": identity_provider,
        "uid": account.uid,
        "username": account.username,
        "provider_domain": account.provider_domain
    }
    to_account = db.query(SocialAuthAccount).filter_by(**args).first()
    if to_account is None:
        for k in ['extra_data', 'picture_url']:
            args[k] = getattr(account, k)
        to_account = account.__class__(**args)
        db.add(to_account)
    return to_account


def find_or_create_urlref(db, urlref):
    from assembl.models import URIRefDb
    assert isinstance(urlref, URIRefDb)
    to_urlref = db.query(URIRefDb).filter_by(val=urlref.val).first()
    if to_urlref is None:
        to_urlref = URIRefDb(val=urlref.val)
        db.add(to_urlref)
    return to_urlref


def find_or_create_agent_profile(db, profile):
    from assembl.models import (
        AgentProfile, SocialAuthAccount, User)
    assert isinstance(profile, AgentProfile)
    accounts = []
    profiles = set()
    for account in profile.accounts:
        if isinstance(account, SocialAuthAccount):
            eq = find_or_create_provider_account(db, account)
        else:
            eq = find_or_create_object(account)
        if eq.profile:
            profiles.add(eq.profile)
        accounts.append(eq)
    if not profiles:
        cols = ['name', 'description']
        # if isinstance(profile, User):
        #     cols += ["preferred_email", "timezone"]
        new_profile = AgentProfile(**{k: getattr(profile, k) for k in cols})
        db.add(new_profile)
    else:
        user_profiles = {p for p in profiles if isinstance(p, User)}
        if user_profiles:
            new_profile = user_profiles.pop()
            profiles.remove(new_profile)
        else:
            new_profile = profiles.pop()
        while profiles:
            new_profile.merge(profiles.pop())
    for account in accounts:
        if account.profile is None:
            account.profile = new_profile
            db.add(account)
    return new_profile


def find_or_create_user_template(db, template):
    pass

def print_path(path):
    print([(x, y.__class__.__name__, y.id) for (x, y) in path])


def prefetch(session, discussion_id):
    from assembl.lib.sqla import class_registry
    from assembl.models import DiscussionBoundBase
    for name, cls in class_registry.items():
        if (isclass(cls) and issubclass(cls, DiscussionBoundBase)
                and not isabstract(cls)):
            mapper = class_mapper(cls)
            undefers = [undefer(attr.key) for attr in mapper.iterate_properties
                        if getattr(attr, 'deferred', False)]
            conditions = cls.get_discussion_conditions(discussion_id)
            poly = with_polymorphic(cls, "*")
            session.query(poly).filter(
                and_(*conditions)).options(*undefers).all()


def recursive_fetch(ob, visited=None):
    # Not used
    visited = visited or {ob}
    mapper = class_mapper(ob.__class__)

    for attr in mapper.iterate_properties:
        if getattr(attr, 'deferred', False):
            getattr(ob, attr.key)
    for reln in mapper.relationships:
        subobs = getattr(ob, reln.key)
        if not subobs:
            continue
        if not isinstance(subobs, list):
            subobs = [subobs]
        for subob in subobs:
            if subob in visited:
                continue
            visited.add(subob)
            if is_special_class(subob):
                continue
            recursive_fetch(subob, visited)

class_info = {}
TRAVERSE_ONE_TO_MANY = {
    "LangString": ("entries",),
}

TREAT_AS_NON_NULLABLE = {
    "Content": ("subject", "body"),
}


def get_mapper_info(mapper):
    from assembl.lib.history_mixin import TombstonableMixin
    from assembl.models import LangStringEntry
    if mapper not in class_info:
        pk_keys_cols = set(mapper.primary_key)
        direct_reln = {r for r in mapper.relationships
                       if r.direction.name == 'MANYTOONE'
                       and r.viewonly == False
                       and not r.local_remote_pairs[0][0].primary_key}
        direct_reln_cols = set(itertools.chain(
            *[r.local_columns for r in direct_reln]))
        avoid_columns = pk_keys_cols.union(direct_reln_cols)
        copy_col_props = {a for a in mapper.iterate_properties
                          if isinstance(a, ColumnProperty)
                          and not avoid_columns.intersection(set(a.columns))}
        if issubclass(mapper.class_, TombstonableMixin):
            # It might have been excluded by a relation.
            copy_col_props.add(mapper._props['tombstone_date'])
        non_nullable_reln = {
            r
            for r in direct_reln
            if any(not c.nullable for c in r.local_columns)
        }

        treat_as_non_nullable = []
        for cls in mapper.class_.mro():
            relns = TREAT_AS_NON_NULLABLE.get(cls.__name__, ())
            if relns:
                treat_as_non_nullable.extend(relns)
        if treat_as_non_nullable:
            for name in treat_as_non_nullable:
                non_nullable_reln.add(mapper.relationships[name])
        nullable_relns = direct_reln - non_nullable_reln
        one_to_many_relns = TRAVERSE_ONE_TO_MANY.get(
            mapper.class_.__name__, ())
        if one_to_many_relns:
            nullable_relns.update(
                {mapper.relationships[n] for n in one_to_many_relns})
        class_info[mapper] = (
            direct_reln, copy_col_props, nullable_relns, non_nullable_reln)
    return class_info[mapper]


def assign_dict(values, r, subob):
    assert r.direction.name == 'MANYTOONE'
    values[r.key] = subob
    for col in r.local_columns:
        if col.foreign_keys:
            fkcol = next(iter(col.foreign_keys)).column
            k = next(iter(r.local_columns))
            values[col.key] = getattr(subob, fkcol.key)
            return
    print("assign_dict: missing foreign key?")


def assign_ob(ob, r, subob):
    if r.direction.name != 'MANYTOONE' and r.mapper != ob.__class__.__mapper__:
        "DISCARDING", r
        # Handled by the reverse connection
        return
    for col in r.local_columns:
        if col.foreign_keys:
            fkcol = next(iter(col.foreign_keys)).column
            k = next(iter(r.local_columns))
            setattr(ob, col.key, getattr(subob, fkcol.key))
            return
    setattr(ob, r.key, subob)
    print("assign_ob: missing foreign key?")


class JoinColumnsVisitor(ClauseVisitor):
    def __init__(self, cls, query, classes_by_table):
        super(JoinColumnsVisitor, self).__init__()
        self.base_class = cls
        self.classes = {cls}
        self.column = None
        self.query = query
        self.classes_by_table = classes_by_table
        self.missing = []

    def is_known_class(self, cls):
        if cls in self.classes:
            return True
        for other_cls in self.classes:
            if issubclass(cls, other_cls) or issubclass(other_cls, cls):
                self.classes.add(cls)
                return True

    def base_class_for_table(self, table):
        classes = self.classes_by_table[table]
        cls = classes[0]
        for other in classes[1:]:
            if issubclass(cls, other):
                cls = other
        return cls

    def process_column(self, column):
        from assembl.lib.history_mixin import TombstonableMixin
        source_cls = self.base_class_for_table(column.table)
        classes = [self.base_class_for_table(foreign_key.column.table)
                   for foreign_key in getattr(column, 'foreign_keys', ())]
        if not classes:
            return self.is_known_class(source_cls)
        dest_cls = classes[0]
        classes.append(source_cls)
        if all((self.is_known_class(c) for c in classes)):
            return True
        if all((not self.is_known_class(c) for c in classes)):
            return False
        orm_relns = [r for r in source_cls.__mapper__.relationships
                     if column in r.local_columns and r.secondary is None]
        if len(orm_relns) > 1 and (
                issubclass(dest_cls, TombstonableMixin) or
                issubclass(source_cls, TombstonableMixin)):
            orm_relns = [
                r for r in orm_relns
                if "tombstone_date" not in str(r.primaryjoin)]
        if len(orm_relns) != 1:
            print("wrong orm_relns for %s.%s : %s" % (
                column.table.name, column.name, str(orm_relns)))
        rattrib = getattr(source_cls, orm_relns[0].key)
        self.query = self.query.join(dest_cls, rattrib)
        self.classes.add(source_cls)
        self.classes.add(dest_cls)
        return True

    def final_query(self):
        while len(self.missing):
            missing = [
                column
                for column in self.missing
                if not self.process_column(column)
            ]

            if len(missing) == len(self.missing):
                break
            self.missing = missing
        assert not self.missing
        return self.query

    def visit_column(self, column):
        if not self.process_column(column):
            self.missing.append(column)


def delete_discussion(session, discussion_id):
    from assembl.models import (
        Base, Discussion, DiscussionBoundBase, Preferences, LangStringEntry)
    # delete anything related first
    classes = [m.class_ for m in Base.registry.mappers]
    classes_by_table = defaultdict(list)
    for cls in classes:
        if isclass(cls):
            classes_by_table[getattr(cls, '__table__', None)].append(cls)
    # Only direct subclass of abstract

    def is_concrete_class(cls):
        if isabstract(cls):
            return False
        for (i, cls) in enumerate(cls.mro()):
            if not i:
                continue
            if not issubclass(cls, Base):
                continue
            return isabstract(cls)

    concrete_classes = set([cls for cls in itertools.chain(
                                *list(classes_by_table.values()))
                            if issubclass(cls, DiscussionBoundBase) and
                            is_concrete_class(cls)])
    concrete_classes.add(Preferences)
    concrete_classes.add(LangStringEntry)
    tables = DiscussionBoundBase.metadata.sorted_tables
    # Special case for preferences
    discussion = session.query(Discussion).get(discussion_id)
    if discussion.preferences:
        session.delete(discussion.preferences)
    # tables.append(Preferences.__table__)
    tables.reverse()
    for table in tables:
        if table not in classes_by_table:
            continue
        for cls in classes_by_table[table]:
            if cls not in concrete_classes:
                continue
            print('deleting', cls.__name__)
            query = session.query(cls.id)
            if hasattr(cls, "get_discussion_conditions"):
                conds = cls.get_discussion_conditions(discussion_id)
            else:
                continue
            assert conds
            cond = and_(*conds)
            v = JoinColumnsVisitor(cls, query, classes_by_table)
            v.traverse(cond)
            query = v.final_query().filter(cond)
            if query.count():
                print("*" * 20, "Not all deleted!")
                ids = {x for (x,) in query.all() if x}
                if ids:
                    for subcls in cls.mro():
                        if getattr(subcls, '__tablename__', None):
                            session.execute(subcls.__table__.delete(
                                subcls.__table__.c.id.in_(ids)))
            session.flush()


def clone_discussion(
        from_session, discussion_id, to_session=None, new_slug=None):
    from assembl.models import (
        DiscussionBoundBase, Discussion, Post, User, Preferences, HistoryMixin,
        BaseIdeaWidget, TombstonableMixin, MultiCriterionVotingWidget, LangString)
    global user_refs
    discussion = from_session.query(Discussion).get(discussion_id)
    assert discussion
    prefetch(from_session, discussion_id)
    changes = defaultdict(dict)
    if to_session is None:
        to_session = from_session
        changes[discussion]['slug'] = new_slug or (discussion.slug + "_copy")
    else:
        changes[discussion]['slug'] = new_slug or discussion.slug
    copies_of = {}
    history_new_base_ids = {}
    copies = set()
    in_process = set()
    promises = defaultdict(list)

    def resolve_promises(ob, copy):
        if ob in promises:
            for (o, reln) in promises[ob]:
                print('fullfilling', o.__class__, o.id)
                assign_ob(o, reln, copy)
            del promises[ob]

    def recursive_clone(ob, path):
        if ob in copies_of:
            return copies_of[ob]
        if ob in copies:
            return ob
        if ob in in_process:
            print("in process", ob.__class__, ob.id)
            return None
        if is_special_class(ob):
            if from_session == to_session:
                copy = ob
            else:
                copy = find_or_create_object(ob)
                to_session.flush()
            assert copy is not None
            copies_of[ob] = copy
            return copy
        if isinstance(ob, DiscussionBoundBase):
            assert discussion_id == ob.get_discussion_id()
        print("recursive_clone", end=' ')
        print_path(path)

        mapper = class_mapper(ob.__class__)
        (direct_reln, copy_col_props, nullable_relns, non_nullable_reln
         ) = get_mapper_info(mapper)
        direct_reln_keys = {r.key: next(iter(r.local_columns)).key for r in direct_reln}
        values = {r.key: getattr(ob, r.key, None) for r in copy_col_props}

        print("->", ob.__class__, ob.id)
        in_process.add(ob)
        for r in non_nullable_reln:
            subob = getattr(ob, r.key, None)
            # Special case for tombstones
            if (subob is None and isinstance(ob, TombstonableMixin) and
                    ob.is_tombstone):
                key = next(iter(r._calculated_foreign_keys)).key
                subob_id = getattr(ob, key)
                if subob_id:
                    target_cls = r._dependency_processor.mapper.class_
                    subob = from_session.query(target_cls).get(subob_id)
            # TODO: handle the case of an action on a tomstoned idea
            assert subob is not None
            assert subob not in in_process
            print('recurse ^0', r.key, subob.id)
            result = recursive_clone(subob, path + [(r.key, subob)])
            assert result is not None
            assert result.id
            print('result', result.__class__, result.id)
            assign_dict(values, r, result)
        local_promises = {}
        for r in nullable_relns:
            subob = getattr(ob, r.key, None)
            if subob is not None:
                if isinstance(subob, list) or subob not in copies_of:
                    local_promises[r] = subob
                else:
                    assign_dict(values, r, copies_of[subob])
        values.update(changes[ob])
        if isinstance(ob, Discussion):
            values['table_of_contents'] = None
            values['root_idea'] = None
            values['next_synthesis'] = None
            values['preferences'] = None
        elif isinstance(ob, Preferences):
            # we got here because we're not the default pref
            target_discussion = copies_of[discussion]
            values['name'] = 'discussion_' + target_discussion.slug
            values['cascade_preferences'] = ob.cascade_preferences
        elif isinstance(ob, tuple(user_refs.keys())):
            # WHAT was I trying to do here?
            for cls in ob.__class__.mro():
                if cls in user_refs:
                    user = values.get(user_refs[cls])
                    if not isinstance(user, User):
                        return ob
                    break
        if "session" in signature(ob.__class__.__init__).parameters:
            values["session"] = to_session
        if isinstance(ob, HistoryMixin):
            values['base_id'] = history_new_base_ids.get(
                (ob.__class__, ob.base_id), None)
            # very special case: Langstring may be shared between versions,
            # and that breaks the single-parent promise implicit in sqla.
            # TODO: less temporary solution to this.
            lsk = [k for (k, v) in values.items() if isinstance(v, LangString)]
            for k in lsk:
                v = values.pop(k)
                values[direct_reln_keys[k]] = v.id
            copy = ob.__class__(**values)
            copy._before_insert()  # set the base_id
            if ob.is_tombstone:
                copy.id = None
                copy._before_insert()  # reset a new id
            else:
                copy.id = copy.base_id
            history_new_base_ids[(ob.__class__, ob.base_id)] = copy.base_id
        else:
            copy = ob.__class__(**values)
        # Remove objects created by constructor side-effects
        if isinstance(copy, BaseIdeaWidget):
            if copy.base_idea_link:
                to_session.expunge(copy.base_idea_link)
                copy.base_idea_link = None
            while copy.idea_links:
                copy.idea_links.pop()
        # Now add the object
        to_session.add(copy)
        to_session.flush()
        print("<-", ob.__class__, ob.id, copy.id)
        copies_of[ob] = copy
        copies.add(copy)
        in_process.remove(ob)
        resolve_promises(ob, copy)
        for reln, subob in local_promises.items():
            if isinstance(subob, list):
                for subobel in subob:
                    print('recurse 0', reln.key, subobel.id)
                    result = recursive_clone(subobel, path + [(reln.key, subobel)])
                    if result is None:  # in process
                        print("promising", subobel.__class__, subobel.id, reln.key)
                        promises[subobel].append((copy, reln))
                    else:
                        print("resolving promise", reln.key, result.__class__, result.id)
                        assign_ob(copy, reln, result)
            elif subob in in_process:
                print("promising", subob.__class__, subob.id, reln.key)
                promises[subob].append((copy, reln))
            else:
                print('recurse 0', reln.key, subob.id)
                result = recursive_clone(subob, path + [(reln.key, subob)])
                if result is None:  # in process
                    print("promising", subob.__class__, subob.id, reln.key)
                    promises[subob].append((copy, reln))
                else:
                    print("resolving promise", reln.key, result.__class__, result.id)
                    assign_ob(copy, reln, result)
        to_session.flush()
        return copy

    treating = set()

    def stage_2_rec_clone(ob, path):
        if ob in treating:
            return
        if is_special_class(ob):
            if from_session == to_session:
                copy = ob
            else:
                copy = find_or_create_object(ob)
                to_session.flush()
            assert copy is not None
            copies_of[ob] = copy
            return copy
        print("stage_2_rec_clone", end=' ')
        if isinstance(ob, DiscussionBoundBase):
            assert discussion_id == ob.get_discussion_id()
        print_path(path)
        treating.add(ob)
        if ob in copies_of:
            copy = copies_of[ob]
        elif ob in copies:
            copy = ob
        else:
            copy = recursive_clone(ob, path)
            resolve_promises(ob, copy)
        treating.add(copy)
        mapper = class_mapper(ob.__class__)
        (
            direct_reln, copy_col_props, nullable_relns, non_nullable_reln
        ) = get_mapper_info(mapper)
        for r in mapper.relationships:
            if r in direct_reln:
                continue
            subobs = getattr(ob, r.key)
            if subobs is None:
                continue
            if not isinstance(subobs, list):
                subobs = [subobs]
            for subob in subobs:
                stage_2_rec_clone(subob, path + [(r.key, subob)])
        if isinstance(copy, MultiCriterionVotingWidget):
            # TODO similar for tokens?
            uri_equivs = {}
            uri_qnum = {}
            for vs in copy.vote_specifications:
                j = vs.settings_json
                old_id = j.get('@id', None)
                uri = vs.uri()
                j['@id'] = uri
                vs.settings_json = j
                if old_id:
                    uri_equivs[old_id] = uri
                uri_qnum[vs.question_id] = uri
            j = copy.settings_json
            for qnum, item in enumerate(j['items']):
                for spec in item['vote_specifications']:
                    old_id = spec["@id"]
                    spec["@id"] = uri_equivs.get(old_id, uri_qnum.get(qnum, old_id))
            copy.settings_json = j

    path = [('', discussion)]
    copy = recursive_clone(discussion, path)
    stage_2_rec_clone(discussion, path)
    to_session.flush()
    for p in to_session.query(Post).filter_by(
            discussion=copy, parent_id=None).all():
        p._set_ancestry('')
    to_session.flush()
    return copy


def engine_from_settings(config, full_config=False):
    settings = get_appsettings(config, 'idealoom')
    db_schema = settings['db_schema']
    set_config(settings, True)
    session = None
    if full_config:
        env = bootstrap(config)
        configure_zmq(settings['changes_socket'], False)
        configure_model_watcher(env['registry'], 'idealoom')
        logging.config.fileConfig(config)
        session = get_session_maker()
        metadata = get_metadata()
    else:
        session = make_session_maker(zope_tr=True)
        import assembl.models
        from assembl.lib.sqla import class_registry
        engine = configure_engine(settings, session_maker=session)
        metadata = get_metadata()
        metadata.bind = engine
        session = sessionmaker(engine)()
    return (metadata, session)


def copy_discussion(source_config, dest_config, source_slug, dest_slug,
                    delete=False, debug=False, permissions=None):
    if (session_maker_is_initialized() and abspath(source_config) == get_config()["__file__"]):
        # not running from script
        dest_session = get_session_maker()()
        dest_metadata = get_metadata()
    else:
        dest_metadata, dest_session = engine_from_settings(
            dest_config, True)
    dest_tables = dest_metadata.sorted_tables
    if source_config != dest_config:
        from assembl.lib.sqla import _session_maker
        temp = _session_maker
        assert temp == dest_session
        source_metadata, source_session = engine_from_settings(
            source_config, False)
        source_tables_by_name = {
            table.name: table.tometadata(source_metadata, source_metadata.schema)
            for table in dest_tables
        }
        _session_maker = dest_session
    else:
        source_metadata, source_session = dest_metadata, dest_session
    try:
        init_key_for_classes(dest_session)
        from assembl.models import Discussion
        discussion = source_session.query(Discussion).filter_by(
            slug=source_slug).one()
        assert discussion, "No discussion named " + source_slug
        permissions = [x.split('+') for x in permissions or ()]
        for (role, permission) in permissions:
            assert role in SYSTEM_ROLES
            assert permission in ASSEMBL_PERMISSIONS
        existing = dest_session.query(Discussion).filter_by(slug=dest_slug).first()
        if existing:
            if delete:
                print("deleting", dest_slug)
                with transaction.manager:
                    delete_discussion(dest_session, existing.id)
            else:
                print("Discussion", dest_slug, end=' ')
                print("already exists! Add -d to delete it.")
                exit(0)
        from assembl.models import Role, Permission, DiscussionPermission
        with dest_session.no_autoflush:
            copy = clone_discussion(
                source_session, discussion.id, dest_session, dest_slug)
            for (role, permission) in permissions:
                role = dest_session.query(Role).filter_by(name=role).one()
                permission = dest_session.query(Permission).filter_by(
                    name=permission).one()
                # assumption: Not already defined.
                dest_session.add(DiscussionPermission(
                    discussion=copy, role=role, permission=permission))
    except Exception:
        traceback.print_exc()
        if debug:
            pdb.post_mortem()
        capture_exception()
    return dest_session

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "configuration",
        help="configuration file with destination database configuration")
    parser.add_argument("-n", "--new_name", help="slug of new discussion")
    parser.add_argument("-d", "--delete", action="store_true", default=False,
                        help="delete discussion copy if exists")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enter pdb on failure")
    parser.add_argument(
        "-s", "--source_db_configuration",
        help="""configuration file with source database configuration, if distinct.
        Be aware that ODBC.ini settings are distinct.""")
    parser.add_argument("discussion", help="original discussion slug")
    parser.add_argument("-p", "--permissions", action="append", default=[],
                        help="Add a role+permission pair to the copy "
                        "(eg system.Authenticated+admin_discussion)")
    args = parser.parse_args()
    new_name = args.new_name or (
        args.discussion + ("" if args.source_db_configuration else "_copy"))
    with transaction.manager:
        session = copy_discussion(
            args.source_db_configuration or args.configuration,
            args.configuration,
            args.discussion, new_name,
            args.delete, args.debug, args.permissions)
