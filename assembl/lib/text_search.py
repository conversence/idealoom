from collections import defaultdict

from sqlalchemy.sql import func, case
from sqlalchemy.sql.expression import or_
from sqlalchemy.orm import (
    joinedload_all, aliased, subqueryload_all, undefer)

from assembl.lib.config import get


postgres_language_configurations = {
    'da': 'danish',
    'nl': 'dutch',
    'en': 'english',
    'fi': 'finnish',
    'fr': 'french',
    'de': 'german',
    'hu': 'hungarian',
    'it': 'italian',
    'no': 'norwegian',
    'pt': 'portuguese',
    'ro': 'romanian',
    'ru': 'russian',
    'es': 'spanish',
    'sv': 'swedish',
    'tr': 'turkish',
    'simple': 'simple',
}


def update_indices(db):
    desired = get('active_text_indices', 'en')
    schema = get('db_schema', 'public')
    prefix = 'langstring_entry_text_'
    result = list(db.execute(
        """SELECT indexname FROM pg_catalog.pg_indexes
        WHERE schemaname = '%s'
        AND tablename = 'langstring_entry'""" % (schema,)))
    existing = {name[len(prefix):] for (name,) in result if name.startswith(prefix)}
    desired = set(desired.split())
    desired.add('simple')
    commands = []
    for locale in existing - desired:
        commands.append('DROP INDEX %s.%s%s' % (schema, prefix, locale))
    for locale in desired - existing:
        pg_name = postgres_language_configurations[locale]
        command = """CREATE INDEX %(prefix)s%(locale)s
        ON %(schema)s.langstring_entry
        USING GIN (to_tsvector('%(pg_name)s', value))""" % {
            'schema': schema, 'pg_name': pg_name,
            'locale': locale, 'prefix': prefix}
        if locale != 'simple':
            command += " WHERE locale = '%(locale)s' OR locale like '%(locale)s_%%%%'" % {
                'locale': locale}
        commands.append(command)
    for command in commands:
        print(command)
        db.execute(command)
    return bool(commands)


def add_text_search(query, join_column, keywords, locales, include_rank=True):
    from assembl.models.langstrings import LangStringEntry
    rank = None
    keywords_j = ' & '.join(keywords)
    lse = aliased(LangStringEntry)
    query = query.join(lse, lse.langstring_id == join_column)
    if locales:
        active_text_indices = get('active_text_indices', 'en')
        locales_by_config = defaultdict(list)
        any_locale = 'any' in locales
        for locale in locales:
            fts_config = postgres_language_configurations.get(locale, 'simple')
            if fts_config not in active_text_indices:
                fts_config = 'simple'
            locales_by_config[fts_config].append(locale)
        conds = {}
        # TODO: to_tsquery vs plainto_tsquery vs phraseto_tsquery
        for fts_config, locales in locales_by_config.items():
            conds[fts_config] = (
                or_(*[((lse.locale == locale) | lse.locale.like(locale + "_%"))
                    for locale in locales]) if 'any' not in locales else None,
                func.to_tsvector(fts_config, lse.value))
        filter = [cond & v.match(keywords_j, postgresql_regconfig=conf)
                  for (conf, (cond, v)) in conds.items()
                  if cond is not None]
        if any_locale:
            (_, v) = conds['simple']
            filter.append(v.match(keywords_j, postgresql_regconfig='simple'))
        query = query.filter(or_(*filter))
        if include_rank:
            if len(conds) > 1:
                if any_locale:
                    (_, v) = conds['simple']
                    else_case = func.ts_rank(v, func.to_tsquery('simple', keywords_j))
                else:
                    else_case = 0
                rank = case([
                    (cond, func.ts_rank(v, func.to_tsquery(conf, keywords_j)))
                    for (conf, (cond, v)) in conds.items()
                    if cond is not None], else_ = else_case).label('score')
            else:
                (conf, (cond, v)) = next(iter(conds.items()))
                rank = func.ts_rank(v, func.to_tsquery(conf, keywords_j)).label('score')
            query = query.add_column(rank)
    else:
        fts_config = 'simple'
        query = query.filter(
            func.to_tsvector(fts_config, lse.value
                ).match(keywords_j, postgresql_regconfig=fts_config))
        if include_rank:
            rank = func.ts_rank(
                func.to_tsvector(fts_config, lse.value),
                func.to_tsquery(fts_config, keywords_j)).label('score')
            query = query.add_column(rank)
    return query, rank
