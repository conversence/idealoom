from abc import abstractmethod
from itertools import groupby

from sqlalchemy import (
    Column, ForeignKey, Integer, String, Boolean)
from sqlalchemy.orm import relationship, reconstructor
from jsonpath_ng.ext import parse
from future.utils import string_types

from . import DiscussionBoundBase, Base
from ..auth import Permissions
from ..lib.sqla import PromiseObjectImporter, get_named_object
from ..lib.sqla_types import URLString
from ..lib.utils import get_global_base_url
from .import_records import ImportRecord
from .generic import ContentSource
from ..tasks.source_reader import PullSourceReader, ClientError, IrrecoverableError


class ImportRecordSource(ContentSource, PromiseObjectImporter):
    __tablename__ = 'import_record_source'
    id = Column(Integer, ForeignKey(ContentSource.id), primary_key=True)
    source_uri = Column(URLString, nullable=False)
    data_filter = Column(String)  # jsonpath-based, assuming json data
    import_records = relationship(ImportRecord, backref="source")
    update_back_imports = Column(Boolean)

    __mapper_args__ = {
        'polymorphic_identity': 'import_record_source',
    }

    def __init__(self, *args, **kwargs):
        super(ImportRecordSource, self).__init__(*args, **kwargs)
        self.init_on_load()

    def login(self):
        return True

    @reconstructor
    def init_on_load(self):
        self.parsed_data_filter = parse(self.data_filter) if self.data_filter else None
        self.global_url = get_global_base_url() + "/data/"

    def init_importer(self):
        super(ImportRecordSource, self).init_importer()
        self.back_import_ids = set()
        self.load_previous_records()

    def base_source_uri(self):
        return self.source_uri

    def load_previous_records(self):
        records = list(self.import_records)
        records.sort(key=lambda r: str(r.target_table))
        to_delete = set()
        for (table_id, recs) in groupby(records, lambda r: r.target_table):
            recs = list(recs)
            cls = ImportRecord.target.property.type_mapper.value_to_class(table_id, None)
            instances = self.db.query(cls).filter(cls.id.in_([r.target_id for r in recs]))
            instance_by_id = {i.id: i for i in instances}
            for r in recs:
                eid = self.normalize_id(r.external_id)
                instance = instance_by_id.get(r.target_id, None)
                if instance is None:
                    # instance was deleted outside.
                    # TODO: cascade generic pointers.
                    to_delete.add(r)
                else:
                    self.instance_by_id[eid] = instance
        self.import_record_by_eid = {
            rec.external_id: rec for rec in records
            if rec not in to_delete}
        for rec in to_delete:
            rec.delete()

    def external_id_to_uri(self, external_id):
        if '//' in external_id:
            return external_id
        return self.source_uri + external_id

    def uri_to_external_id(self, uri):
        base = self.source_uri
        if uri.startswith(base):
            uri = uri[len(base):]
        return uri

    def find_record(self, uri):
        external_id = self.uri_to_external_id(uri)
        return self.db.query(ImportRecord).filter_by(
            source_id=self.id,
            external_id=external_id).first()

    def generate_message_id(self, source_post_id):
        return source_post_id

    def id_from_data(self, data):
        if isinstance(data, dict):
            data = data.get('@id', None)
        if isinstance(data, string_types):
            return data
        # TODO: array of ids...

    def get_imported_from_in_data(self, data):
        return None

    def normalize_id(self, id):
        id = self.id_from_data(id)
        if not id:
            return
        id = super(ImportRecordSource, self).normalize_id(id)
        if id.startswith('local:'):
            return self.source_uri + id[6:]
        return id

    def get_object(self, id, default=None):
        id = self.normalize_id(id)
        instance = super(ImportRecordSource, self).get_object(id, default)
        if instance:
            return instance
        record = self.db.query(ImportRecord).filter_by(
            source=self, external_id=id).first()
        if record:
            return record.target

    def base_set_item(self, id, instance):
        # without adding an import record
        PromiseObjectImporter.__setitem__(self, id, instance)

    def __setitem__(self, id, instance):
        id = self.normalize_id(id)
        exists = id in self.instance_by_id
        super(ImportRecordSource, self).__setitem__(id, instance)
        if exists:
            return
        self.db.add(ImportRecord(
            source=self, target=instance, external_id=id))

    @abstractmethod
    def class_from_data(self, data):
        return None

    def process_data(self, data):
        return data

    @abstractmethod
    def read(self, admin_user_id, base=None):
        self.init_importer()

    def read_data_gen(self, data_gen, admin_user_id, apply_filter=False):
        ctx = self.discussion.get_instance_context(user_id=admin_user_id)
        remainder = []
        for data in data_gen:
            ext_id = self.id_from_data(data)
            if not ext_id:
                continue
            imported_from = self.get_imported_from_in_data(data)
            if imported_from and imported_from in self.local_urls:
                short_form = 'local:' + imported_from[len(self.global_url):]
                target = get_named_object(short_form)
                assert target
                # do not create ImportRecord
                PromiseObjectImporter.__setitem__(self, ext_id, target)
                self.back_import_ids.add(ext_id)
                if not self.update_back_imports:
                    continue
            remainder.append(data)
        data_gen = remainder
        if apply_filter and self.parsed_data_filter:
            filtered = [
                x.value for x in self.parsed_data_filter.find(data_gen)]
            filtered_ids = {self.id_from_data(data) for data in filtered}
            data_gen = filtered
        for data in data_gen:
            ext_id = self.id_from_data(data)
            if not ext_id:
                continue
            pdata = self.process_data(data)
            if not pdata:
                continue
            if ext_id in self:
                if self.normalize_id(ext_id) in self.import_record_by_eid or (
                        ext_id in self.back_import_ids and self.update_back_imports):
                    target = self[ext_id]
                    permissions = ctx.get_permissions()
                    if Permissions.ADMIN_DISC in permissions:
                        permissions.append(target.crud_permissions.update_owned)
                    target.update_from_json(
                        pdata, context=ctx, object_importer=self, permissions=permissions,
                        parse_def_name='import')
            else:
                cls = self.class_from_data(data)
                if not cls:
                    self[ext_id] = None
                    continue
                # Don't we need a CollectionCtx?
                instance_ctx = cls.create_from_json(
                    pdata, ctx, object_importer=self, parse_def_name='import')
                if instance_ctx:
                    instance = instance_ctx._instance
                    self.process_new_object(ext_id, instance)
                    self.db.add(instance)
        if self.pending():
            self.resolve_pending()
        self.db.flush()
        # Maybe tombstone objects that had import records and were not reimported or referred to?

    def resolve_pending(self):
        """resolve any pending reference, may require queries. May fail."""
        pass

    def process_new_object(self, ext_id, instance):
        self[ext_id] = instance

    def make_reader(self):
        return SimpleImportReader(self.id)


class SimpleImportReader(PullSourceReader):
    def __init__(self, source_id):
        super(SimpleImportReader, self).__init__(source_id)

    def login(self):
        try:
            login = self.source.login()
            if not login:
                raise IrrecoverableError("could not login")
        except AssertionError:
            raise ClientError("login connection error")

    def do_read(self):
        sess = self.source.db
        try:
            self.source.read()
            sess.commit()
        except Exception as e:
            self.new_error(e)
