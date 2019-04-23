"""Classes for multilingual strings, using automatic or manual translation"""
from builtins import next
from builtins import filter
from collections import defaultdict
from datetime import datetime

from future.utils import as_native_str, string_types
from sqlalchemy import (
    Column, ForeignKey, Integer, Boolean, String, SmallInteger,
    UnicodeText, UniqueConstraint, event, inspect, Sequence, events,
    literal)
from sqlalchemy.sql.expression import case
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import (
    relationship, backref, subqueryload, joinedload, aliased,
    attributes, remote, foreign)
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.ext.declarative import declared_attr
import simplejson as json

from ..lib.sqla_types import CoerceUnicode
from . import Base, TombstonableMixin, CrudOperation
from .import_records import ImportRecord
from ..lib import config
from ..lib.abc import classproperty
from ..lib.locale import locale_ancestry, create_mt_code, locale_compatible
from ..auth import CrudPermissions, P_READ, P_ADMIN_DISC, P_SYSADMIN


class LocaleLabel(Base):
    "Allows to obtain the name of locales (in any target locale, incl. itself)"

    __tablename__ = "locale_label"
    __table_args__ = (UniqueConstraint('named_locale', 'locale_of_label'), )
    id = Column(Integer, primary_key=True)
    named_locale = Column(String(11), nullable=False, index=True)
    locale_of_label = Column(String(11), nullable=False, index=True)
    name = Column(CoerceUnicode)
    UNDEFINED = "und"
    NON_LINGUISTIC = "zxx"
    MULTILINGUAL = "mul"
    SPECIAL_LOCALES = [UNDEFINED, NON_LINGUISTIC, MULTILINGUAL]

    """Note: The name of locales follow Posix locale conventions: lang(_Script)(_COUNTRY),
    (eg zh_Hant_HK, but script can be elided (eg fr_CA) if only one script for language,
    as per http://www.iana.org/assignments/language-subtag-registry/language-subtag-registry
    """

    @classmethod
    def names_in_locale(cls, locale):
        locale_chain = locale_ancestry(locale)
        locale_labels = locale.db.query(cls).filter(
            cls.locale_of_label.in_(locale_chain)).all()
        by_target = defaultdict(list)
        for ln in locale_labels:
            by_target[ln.locale_of_label].append(ln)
        result = dict()
        locale_chain.reverse()
        for locale in locale_chain:
            result.update({
                lname.named_locale: lname.name
                for lname in by_target[locale]})
        return result

    @classmethod
    def names_of_locales_in_locale(cls, loc_codes, target_locale):
        target_locs = locale_ancestry(target_locale)
        locale_labels = cls.default_db.query(cls).filter(
            cls.locale_of_label.in_(target_locs),
            cls.named_locale.in_(loc_codes)).all()
        by_target = defaultdict(list)
        for ln in locale_labels:
            by_target[ln.locale_of_label].append(ln)
        result = dict()
        target_locs.reverse()
        for loc in target_locs:
            result.update({
                lname.named_locale: lname.name
                for lname in by_target[loc]})
        return result

    @classmethod
    def names_in_self(cls):
        return {
            lname.named_locale: lname.name
            for lname in cls.default_db.query(cls).filter(
                cls.locale_of_label == cls.named_locale)}

    @classmethod
    def load_names(cls, db=None):
        from os.path import dirname, join
        db = db or cls.default_db
        fname = join(dirname(dirname(__file__)),
                     'nlp/data/language-names.json')
        with open(fname, encoding='utf-8') as f:
            names = json.load(f, encoding="utf-8")
        locales = {x[0] for x in names}.union({x[1] for x in names})
        count_locales = db.query(cls.named_locale.label('loc')).union(db.query(cls.locale_of_label.label('loc'))).distinct().count()
        count_names = db.query(cls.id).count()
        if count_names == len(names) and count_locales == len(locales):
            # shortcut
            return
        existing = set(db.query(cls.named_locale, cls.locale_of_label).all())
        missing = []
        for (lcode, tcode, name) in names:
            if (lcode, tcode) not in existing:
                missing.append(cls(
                    named_locale=lcode, locale_of_label=tcode, name=name))
        db.bulk_save_objects(missing)
        db.flush()

    @classmethod
    def populate_db(cls, db=None):
        db.execute("lock table %s in exclusive mode" % cls.__table__.name)
        cls.load_names(db)

    crud_permissions = CrudPermissions(P_READ, P_ADMIN_DISC)


class LangString(Base):
    """A multilingual string, composed of many :py:class:`LangStringEntry`"""
    __tablename__ = "langstring"

    @classmethod
    def subqueryload_option(cls, reln):
        return subqueryload(reln).joinedload(cls.entries)

    @classmethod
    def joinedload_option(cls, reln):
        return joinedload(reln).joinedload(cls.entries)

    id_sequence_name = "langstring_idsequence"

    @classproperty
    def id_sequence(cls):
        return Sequence(cls.id_sequence_name, schema=cls.metadata.schema)

    id = Column(Integer, primary_key=True)

    @declared_attr
    def import_record(cls):
        return relationship(
            ImportRecord, uselist=False,
            primaryjoin=(remote(ImportRecord.target_id)==foreign(cls.id)) &
                        (ImportRecord.target_table == cls.__tablename__))

    def __bool__(self):
        for entry in self.entries:
            if entry:
                return True
        return False

    def as_jsonld(self, default_lang=None, use_map=False):
        entries = [e.as_jsonld(default_lang) for e in self.entries]
        if len(self.entries) == 1:
            return self.entries[0].as_jsonld(default_lang)
        elif use_map:
            return {e.locale: e.value for e in self.entries}
        else:
            return [e.as_jsonld(default_lang) for e in self.entries]

    def _before_insert(self):
        if self.using_virtuoso:
            # This is a virtuoso workaround: virtuoso does not like
            # empty inserts.
            (id,) = self.db.execute(
                self.id_sequence.next_value().select()).first()
            self.id = id

    def add_entry(self, entry, allow_replacement=True):
        """Add a LangStringEntry to the langstring.
        Previous versions with the same language will be tombstoned,
        and translations based on such a version will be suppressed."""
        if entry and isinstance(entry, LangStringEntry):
            entry_locale = entry.locale
            for ex_entry in self.entries:
                # Loop on the entries means that repeated calls to
                # add_entry will be O(n^2). If this becomes an issue,
                # create an add_entries method.
                if ex_entry is entry:
                    continue
                if ex_entry.value == entry.value:
                    if entry in self.entries:
                        self.entries.remove(entry)
                    return ex_entry
                ex_locale = ex_entry.locale
                if entry_locale == ex_locale:
                    if ex_entry.is_machine_translated:
                        self.entries.remove(ex_entry)
                    else:
                        if not allow_replacement:
                            return None
                        ex_entry.is_tombstone = True
                        self.remove_translations_of(ex_entry)
                        if inspect(self).persistent:
                            self.db.expire(self, ["entries"])
            entry.langstring = self
            return entry

    def remove_translations_of(self, entry):
        """Remove all translations based on this code."""
        if entry.id is None:
            return
        for trans in self.entries[:]:
            if trans.mt_trans_of_id == entry.id:
                trans.delete()

    @as_native_str()
    def __repr__(self):
        return 'LangString (%d): %s\n' % (
            self.id or -1, "\n".join((repr(x) for x in self.entries)))

    @classmethod
    def create(cls, value, locale_code=LocaleLabel.UNDEFINED):
        ls = cls()
        lse = LangStringEntry(
            langstring=ls, value=value,
            locale=locale_code)
        return ls

    def add_value(self, value, locale_code=LocaleLabel.UNDEFINED,
                  allow_replacement=True):
        return self.add_entry(LangStringEntry(
            langstring=self, value=value,
            locale=locale_code),
            allow_replacement=allow_replacement)

    @classmethod
    def create_localized_langstring(
            cls, trans_string, desired_locales=None, known_translations=None):
        """Construct a langstring from a localized string.
        Call with a TranslationString."""
        inst = cls.create(trans_string, 'en')
        known_translations = known_translations or {}
        for loc in desired_locales or ():
            if loc == 'en':
                continue
            elif loc in known_translations:
                inst.add_value(known_translations[loc], loc)
            else:
                from pyramid.i18n import make_localizer
                from os.path import dirname, join
                loc_dir = join(dirname(dirname(__file__)), 'locale')
                localizer = make_localizer(loc, loc_dir)
                inst.add_value(localizer.translate(trans_string), loc)
        return inst

    @property
    def entries_as_dict(self):
        return {e.locale: e for e in self.entries}

    @hybrid_method
    def non_mt_entries(self):
        return [e for e in self.entries
                if not e.is_machine_translated]

    @non_mt_entries.expression
    def non_mt_entries(self):
        return self.db.query(LangStringEntry).filter(
            ~LangStringEntry.is_machine_translated).subquery()

    def first_original(self):
        return next(iter(self.non_mt_entries()))

    @classmethod
    def EMPTY(cls, db=None):
        ls = LangString()
        e = LangStringEntry(
            langstring=ls,
            locale=LocaleLabel.NON_LINGUISTIC)
        if db is not None:
            db.add(e)
            db.add(ls)
        return ls

    @classmethod
    def reset_cache(cls):
        pass

    # Which object owns this?
    owner_object = None
    _owning_relns = []

    @classmethod
    def setup_ownership_load_event(cls, owner_class, relns):
        def load_owner_object(target, context):
            for reln in relns:
                ls = getattr(target, reln, None)
                if ls is not None:
                    ls.owner_object = target
        event.listen(owner_class, "load", load_owner_object, propagate=True)
        event.listens_for(owner_class, "refresh", load_owner_object, propagate=True)
        def set_owner_object(target, value, old_value, initiator):
            if old_value is not None:
                old_value.owner_object = None
            if value is not None:
                value.owner_object = target
        for reln in relns:
            cls._owning_relns.append((owner_class, reln))
            event.listen(getattr(owner_class, reln), "set", set_owner_object, propagate=True)

    def get_owner_object(self):
        if self.owner_object is None and inspect(self).persistent:
            self.owner_object = self.owner_object_from_query()
        return self.owner_object

    def owner_object_from_query(self):
        queries = []
        for owning_class, reln_name in self._owning_relns:
            backref_name = owning_class.__mapper__.relationships[reln_name].backref[0]
            query = getattr(self, backref_name)
            query = query.with_entities(owning_class.id, literal(owning_class.__name__).label('classname'))
            queries.append(query)
        query = queries[0].union(*queries[1:])
        data = query.first()
        if data:
            id, cls_name = data
            cls = [cls for (cls, _) in self._owning_relns if cls.__name__ == cls_name][0]
            return self.db.query(cls).filter_by(id=id).first()

    def send_to_changes(self, connection, operation=CrudOperation.DELETE,
                        discussion_id=None, view_def="changes"):
        owner_object = self.get_owner_object()
        if owner_object is not None:
            owner_object.send_to_changes(
                connection, operation, discussion_id, view_def)
        else:
            super(LangString, self).send_to_changes(
                connection, operation, discussion_id, view_def)

    def user_can(self, user_id, operation, permissions):
        owner_object = self.get_owner_object()
        if owner_object is not None:
            return owner_object.user_can(user_id, operation, permissions)
        return super(LangString, self).user_can(user_id, operation, permissions)

    @classmethod
    def _do_create_from_json(
            cls, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        # Special case for JSON-LD
        added = False
        ls = cls()
        def guess_lang(value):
            from .discussion import Discussion
            discussion = context.get_instance_of_class(Discussion)
            if discussion:
                tr_service = discussion.translation_service()
                lang, _ = tr_service.identify(value)
            return LocaleLabel.UNDEFINED

        if isinstance(json, list):
            for entry_record in json:
                value = entry_record['@value']
                if value:
                    added = True
                    lang = entry_record.get('@language', None) or guess_lang(value)
                    ls.add_value(value, lang)
        elif isinstance(json, dict):
            if '@id' in json or '@type' in json:
                return super(LangString, cls)._do_create_from_json(
                    json, parse_def, context,
                    duplicate_handling, object_importer)
            elif '@value' in json:
                value = json['@value']
                if value:
                    added = True
                    lang = json.get('@language', None) or guess_lang(value)
                    ls.add_value(value, lang)
            else:
                for lang, value in json.items():
                    if value:
                        added = True
                        ls.add_value(value, lang)
        elif isinstance(json, string_types):
            if json:
                added = True
                lang = guess_lang(json)
                ls.add_value(json, lang)
        else:
            raise ValueError("Not a valid langstring: " + json)
        i_context = ls.get_instance_context(context)
        if added:
            cls.default_db.add(ls)
        else:
            i_context._instance = None
        return i_context

    def _do_update_from_json(
            self, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        # Special case for JSON-LD
        if isinstance(json, list):
            for entry_record in json:
                lang = entry_record.get('@language', LocaleLabel.UNDEFINED)
                value = entry_record['@value']
                entry = self.entries_as_dict.get(lang, None)
                if entry:
                    entry.set_value(value)
                elif value:
                    self.add_value(value, lang)
        elif isinstance(json, dict):
            if '@id' in json or '@type' in json:
                return super(LangString, self)._do_update_from_json(
                    json, parse_def, context,
                    duplicate_handling, object_importer)
            elif '@value' in json:
                value = json['@value']
                if value:
                    lang = json.get('@language', LocaleLabel.UNDEFINED)
                    entry = self.entries_as_dict.get(lang, None)
                    if entry:
                        entry.set_value(value)
                    elif value:
                        self.add_value(value, lang)
            else:
                for lang, value in json.items():
                    entry = self.entries_as_dict.get(lang, None)
                    if entry:
                        entry.set_value(value)
                    elif value:
                        self.add_value(value, lang)
        elif isinstance(json, string_types):
            from .discussion import Discussion
            lang = LocaleLabel.UNDEFINED
            discussion = context.get_instance_of_class(Discussion)
            if discussion:
                tr_service = discussion.translation_service()
                lang, _ = tr_service.identify(json)
            entry = self.entries_as_dict.get(lang, None)
            if entry:
                entry.set_value(json)
            elif json:
                self.add_value(json, lang)
        else:
            raise ValueError("Not a valid langstring: " + json)
        return self

    # TODO: Reinstate when the javascript can handle empty body/subject.
    # def generic_json(
    #         self, view_def_name='default', user_id=None,
    #         permissions=(P_READ, ), base_uri='local:'):
    #     if self.id == self.EMPTY_ID:
    #         return None
    #     return super(LangString, self).generic_json(
    #         view_def_name=view_def_name, user_id=user_id,
    #         permissions=permissions, base_uri=base_uri)

    @property
    def undefined_entry(self):
        und = LocaleLabel.UNDEFINED
        for x in self.entries:
            if x.locale == und:
                return x

    @hybrid_method
    def best_lang_old(self, locale_codes):
        # based on a simple ordered list of locale_codes
        locale_collection = Locale.locale_collection
        locale_collection_subsets = Locale.locale_collection_subsets
        available = self.entries_as_dict
        if len(available) == 0:
            return LangStringEntry.EMPTY()
        if len(available) == 1:
            # optimize for common case
            return available[0]
        for locale_code in locale_codes:
            # is the locale there?
            if locale_code in available:
                return available[locale_code]
            # is the base locale there?
            root_locale = Locale.extract_root_locale(locale_code)
            if root_locale not in locale_codes:
                locale_id = locale_collection.get(root_locale, None)
                if locale_id and locale_id in available:
                    return available[locale_id]
            # is another variant there?
            mt_variants = list()
            for sublocale in locale_collection_subsets[root_locale]:
                if sublocale in locale_codes:
                    continue
                if sublocale == root_locale:
                    continue
                if Locale.locale_is_machine_translated(sublocale):
                    mt_variants.append(sublocale)
                    continue
                locale_id = locale_collection.get(sublocale, None)
                if locale_id and locale_id in available:
                    return available
        # We found nothing, look at MT variants.
        for sublocale in mt_variants:
            locale_id = locale_collection.get(sublocale, None)
            if locale_id and locale_id in available:
                return available[locale_id]
        # TODO: Look at other languages in the country?
        # Give up and give nothing, or give first?

    @best_lang_old.expression
    def best_lang_old(self, locale_codes):
        # Construct an expression that will find the best locale according to list.
        scores = {}
        current_score = 1
        locale_collection = Locale.locale_collection
        locale_collection_subsets = Locale.locale_collection_subsets
        for locale_code in locale_codes:
            # is the locale there?
            locale_id = locale_collection.get(locale_code, None)
            if locale_id:
                scores[locale_id] = current_score
                current_score += 1
            # is the base locale there?
            root_locale = Locale.extract_root_locale(locale_code)
            if root_locale not in locale_codes:
                locale_id = locale_collection.get(root_locale, None)
                if locale_id:
                    scores[locale_id] = current_score
                    current_score += 1
            # is another variant there?
            mt_variants = list()
            found = False
            for sublocale in locale_collection_subsets[root_locale]:
                if sublocale in locale_codes:
                    continue
                if sublocale == root_locale:
                    continue
                if Locale.locale_is_machine_translated(sublocale):
                    mt_variants.append(sublocale)
                    continue
                locale_id = locale_collection.get(sublocale, None)
                if locale_id:
                    scores[locale_id] = current_score
                    found = True
            if found:
                current_score += 1
        # Put MT variants as last resort.
        for sublocale in mt_variants:
            locale_id = locale_collection.get(sublocale, None)
            if locale_id:
                scores[locale_id] = current_score
                # Assume each mt variant to have a lower score.
                current_score += 1
        c = case(scores, value=LangStringEntry.locale_id,
                 else_=current_score)
        q = Query(LangStringEntry).order_by(c).limit(1).subquery()
        return aliased(LangStringEntry, q)

    def best_lang(self, user_prefs=None, allow_errors=True):
        from .auth import LanguagePreferenceCollection
        # Get the best langStringEntry among those available using user prefs.
        # 1. Look at available original languages: get corresponding pref.
        # 2. Sort prefs (same order as original list.)
        # 3. take first applicable w/o trans or whose translation is available.
        # 4. if none, look at available translations and repeat.
        # Logic is painful, but most of the time (single original)
        # will be trivial in practice.
        if len(self.entries) == 1:
            return self.entries[0]
        if user_prefs:
            if not isinstance(user_prefs, LanguagePreferenceCollection):
                # Often worth doing upstream
                user_prefs = LanguagePreferenceCollection.getCurrent()
            for use_originals in (True, False):
                entries = [e for e in self.entries
                           if e.is_machine_translated != use_originals]
                if not allow_errors:
                    entries = [e for e in entries if not e.error_code]
                if not entries:
                    continue
                candidates = []
                entriesByLocale = {}
                for entry in entries:
                    pref = user_prefs.find_locale(entry.locale)
                    if pref:
                        candidates.append(pref)
                        entriesByLocale[pref.locale] = entry
                    elif use_originals:
                        # No pref for original, just return the original entry
                        return entry
                if candidates:
                    candidates.sort()
                    entries = list(self.entries)
                    if not allow_errors:
                        entries = [e for e in entries if not e.error_code]
                    for pref in candidates:
                        if pref.translate:
                            best = self.closest_entry(pref.translate)
                            if best:
                                return best
                        else:
                            return entriesByLocale[pref.locale]
        # give up and give first original
        entries = self.non_mt_entries()
        if entries:
            return entries[0]
        # or first entry
        return self.entries[0]

    def best_entry_in_request(self):
        from .auth import LanguagePreferenceCollection
        # Use only when a request is in context, eg view_def
        return self.best_lang(
            LanguagePreferenceCollection.getCurrent(), False)

    def best_entries_in_request_with_originals(self):
        from .auth import LanguagePreferenceCollection
        "Give both best and original (for view_def); avoids a roundtrip"
        # Use only when a request is in context, eg view_def
        prefs = LanguagePreferenceCollection.getCurrent()
        lang = self.best_lang(prefs)
        entries = [lang]
        # Punt this.
        # if lang.error_code:
        #     # Wasteful to call twice, but should be rare.
        #     entries.append(self.best_lang(prefs, False))
        if all((e.is_machine_translated for e in entries)):
            entries.extend(self.non_mt_entries())
        return entries

    def closest_entry(self, target_locale):
        def common_len(e):
            return locale_compatible(target_locale, e.locale)
        entries = [(common_len(e), id(e), e) for e in self.entries if not e.error_code]
        if entries:
            entries.sort(reverse=True)
            if entries[0][0]:
                return entries[0][2]

    def remove_translations(self, forget_identification=True):
        for entry in list(self.entries):
            if entry.is_machine_translated:
                entry.delete()
            elif forget_identification:
                entry.forget_identification(True)
        if inspect(self).persistent:
            self.db.expire(self, ["entries"])

    def clone(self, db=None, tombstone=None):
        if tombstone is True:
            tombstone = datetime.utcnow()
        clone = self.__class__()
        db = db or clone.db
        for e in self.entries:
            e = e.clone(clone, db=db, tombstone=tombstone)
        db.add(clone)
        return clone

    # Those permissions are for an ownerless object. Accept Create before ownership.
    crud_permissions = CrudPermissions(P_READ, P_SYSADMIN, P_SYSADMIN, P_SYSADMIN)


if LangString.using_virtuoso:
    @event.listens_for(LangString, 'before_insert', propagate=True)
    def receive_before_insert(mapper, connection, target):
        target._before_insert()


class LangStringEntry(TombstonableMixin, Base):
    """A string bound to a given locale. Many of those form a :py:class:`LangString`"""
    __tablename__ = "langstring_entry"
    __table_args__ = (
        UniqueConstraint("langstring_id", "locale", "tombstone_date"),
    )

    def __init__(self, session=None, *args, **kwargs):
        """ in the kwargs, you can specify locale using locale or @language"""
        if ("locale" not in kwargs and '@language' in kwargs):
            # Create locale on demand.
            kwargs["locale"] = kwargs.get("@language", "und")
            del kwargs["@language"]
        super(LangStringEntry, self).__init__(*args, **kwargs)

    id = Column(Integer, primary_key=True)
    langstring_id = Column(
        Integer, ForeignKey(LangString.id, ondelete="CASCADE"),
        nullable=False, index=True)
    langstring = relationship(
        LangString,
        primaryjoin="LangString.id==LangStringEntry.langstring_id",
        backref=backref(
            "entries",
            primaryjoin="and_(LangString.id==LangStringEntry.langstring_id, "
                        "LangStringEntry.tombstone_date == None)",
            lazy="subquery",
            cascade="all, delete-orphan"))
    # Should we allow locale-less LangStringEntry? (for unknown...)

    locale = Column(String(11), index=True)

    mt_trans_of_id = Column(Integer, ForeignKey(
        'langstring_entry.id', ondelete='CASCADE', onupdate='CASCADE'))

    mt_trans_as = relationship(
        "LangStringEntry", foreign_keys=[mt_trans_of_id],
        backref=backref("mt_trans_of", remote_side=[id]))

    locale_identification_data = Column(String)
    locale_confirmed = Column(
        Boolean, server_default="0",
        doc="Locale inferred from discussion agrees with identification_data")
    error_count = Column(
        Integer, default=0,
        doc="Errors from the translation server")
    error_code = Column(
        SmallInteger, default=None,
        doc="Type of error from the translation server")
    # tombstone_date = Column(DateTime) implicit from Tombstonable mixin
    value = Column(UnicodeText)  # not searchable in virtuoso

    def __bool__(self):
        return bool(self.value)

    @declared_attr
    def import_record(cls):
        return relationship(
            ImportRecord, uselist=False,
            primaryjoin=(remote(ImportRecord.target_id)==foreign(cls.id)) &
                        (ImportRecord.target_table == cls.__tablename__))

    def as_jsonld(self, default_lang=None):
        if self.locale in (default_lang, LocaleLabel.UNDEFINED):
            return self.value
        else:
            return {"@language": self.locale, "@value": self.value}

    def set_value(self, value, clone=True):
        target = self
        if value != self.value:
            if value:
                if clone:
                    target = self.clone(self.langstring, tombstone=True)
                target.value = value
            else:
                target.is_tombstone = True
        return target

    def clone(self, langstring, db=None, tombstone=None):
        if tombstone is True:
            tombstone = datetime.utcnow()
        clone = self.__class__(
            langstring=langstring,
            locale=self.locale,
            value=self.value,
            tombstone_date = self.tombstone_date or (
                tombstone if tombstone else None),
            locale_identification_data=self.locale_identification_data,
            locale_confirmed = self.locale_confirmed,
            error_code=self.error_code,
            error_count=self.error_count)
        db = db or self.db
        db.add(clone)
        return clone

    def populate_from_context(self, context):
        if not(self.langstring or self.langstring_id):
            self.langstring = context.get_instance_of_class(LangString)
        super(LangStringEntry, self).populate_from_context(context)

    @as_native_str()
    def __repr__(self):
        value = self.value or ''
        if len(value) > 50:
            value = value[:50]+'...'
        if self.error_code:
            return (u'%d: [%s, ERROR %d] "%s"' % (
                self.id or -1,
                self.locale or "missing",
                self.error_code,
                value))
        return (u'%d: [%s] "%s"' % (
            self.id or -1,
            self.locale or "missing",
            value))

    @property
    def locale_code(self):
        if self.mt_trans_of_id:
            return create_mt_code(self.mt_trans_of.locale, self.locale)
        else:
            return self.locale

    @property
    def locale_identification_data_json(self):
        return json.loads(self.locale_identification_data)\
            if self.locale_identification_data else {}

    @locale_identification_data_json.setter
    def locale_identification_data_json(self, data):
        self.locale_identification_data = json.dumps(data) if data else None

    @hybrid_property
    def is_machine_translated(self):
        return self.mt_trans_of_id != None

    @is_machine_translated.expression
    def is_machine_translated(cls):
        # Only works if the Locale is part of the join
        return cls.mt_trans_of_id != None

    def identify_locale(self, locale_code, data, certainty=False):
        # A translation service proposes a data identification.
        # the information is deemed confirmed if it fits the initial
        # hypothesis given at LSE creation.
        changed = False
        old_locale_code = self.locale
        langstring = self.langstring or (
            LangString.get(self.langstring_id) if self.langstring_id else None)
        if self.is_machine_translated:
            raise RuntimeError("Why identify a machine-translated locale?")
        data = data or {}
        original = self.locale_identification_data_json.get("original", None)
        if not locale_code or locale_code == LocaleLabel.UNDEFINED:
            if not self.locale or self.locale == LocaleLabel.UNDEFINED:
                # replace id data with new one.
                if original:
                    data['original'] = original
                self.locale_identification_data_json = data
            return False
        elif original and locale_code == original:
            if locale_code != old_locale_code:
                self.locale = locale_code
                changed = True
            self.locale_identification_data_json = data
            self.locale_confirmed = True
        elif locale_code != old_locale_code:
            if self.locale_confirmed:
                if certainty:
                    raise RuntimeError("Conflict of certainty")
                # keep the old confirming data
                return False
            # compare data? replacing with new for now.
            if not original and self.locale_identification_data:
                original = LocaleLabel.UNDEFINED
            original = original or old_locale_code
            if original != locale_code and original != LocaleLabel.UNDEFINED:
                data["original"] = original
            self.locale = locale_code
            changed = True
            self.locale_identification_data_json = data
            self.locale_confirmed = certainty
        else:
            if original and original != locale_code:
                data['original'] = original
            self.locale_identification_data_json = data
            self.locale_confirmed = certainty or locale_code == original
        if changed:
            if langstring:
                langstring.remove_translations_of(self)
                # Re-adding to verify there's no conflict
                added = langstring.add_entry(self, certainty)
                if added is None:
                    # We identified an entry with something that existed
                    # as a known original. Not sure what to do now,
                    # reverting just in case.
                    self.locale_code = old_locale_code
                    changed = False
        return changed

    def forget_identification(self, force=False):
        if force:
            self.locale = LocaleLabel.UNDEFINED
            self.locale_confirmed = False
        elif not self.locale_confirmed:
            data = self.locale_identification_data_json
            orig = data.get("original", None)
            if orig and orig != self.locale:
                self.locale = orig
        self.locale_identification_data = None
        self.error_code = None
        self.error_count = 0

    def send_to_changes(self, connection, operation=CrudOperation.DELETE,
                        discussion_id=None, view_def="changes"):
        if self.langstring is not None:
            self.langstring.send_to_changes(
                connection, operation, discussion_id, view_def)
        else:
            super(LangStringEntry, self).send_to_changes(
                connection, operation, discussion_id, view_def)

    def user_can(self, user_id, operation, permissions):
        if self.langstring is not None:
            return self.langstring.user_can(user_id, operation, permissions)
        return super(LangStringEntry, self).user_can(user_id, operation, permissions)

    # Those permissions are for an ownerless object. Accept Create before ownership.
    crud_permissions = CrudPermissions(P_READ, P_SYSADMIN, P_SYSADMIN, P_SYSADMIN)


# class TranslationStamp(Base):
#     "For future reference. Not yet created."
#     __tablename__ = "translation_stamp"
#     id = Column(Integer, primary_key=True)
#     source = Column(Integer, ForeignKey(LangStringEntry.id))
#     dest = Column(Integer, ForeignKey(LangStringEntry.id))
#     translator = Column(Integer, ForeignKey(User.id))
#     created = Column(DateTime, server_default="now()")
#     crud_permissions = CrudPermissions(
#          P_TRANSLATE, P_READ, P_SYSADMIN, P_SYSADMIN,
#          P_TRANSLATE, P_TRANSLATE)
