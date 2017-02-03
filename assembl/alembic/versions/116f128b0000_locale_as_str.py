"""locale_as_str

Revision ID: 116f128b0000
Revises: 335e41a86a6b
Create Date: 2017-02-02 16:32:08.018010

"""

# revision identifiers, used by Alembic.
revision = '116f128b0000'
down_revision = '335e41a86a6b'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config

rtl_locales = {"ar", "dv", "ha", "he", "fa", "ps", "ur", "yi"}

def is_rtl(locale):
    parts = locale.split("_")
    return parts[0] in rtl_locales or (len(parts) > 1 and parts[1] == 'Arab')

def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'locale_label',
            sa.Column('named_locale', sa.String(11), index=True))
        op.add_column(
            'locale_label',
            sa.Column('locale_of_label', sa.String(11), index=True))
        op.add_column(
            'user_language_preference',
            sa.Column('locale', sa.String(11), index=True))
        op.add_column(
            'user_language_preference',
            sa.Column('translate', sa.String(11)))
        op.add_column(
            'langstring_entry',
            sa.Column('locale', sa.String(11), index=True))
        op.add_column(
            'langstring_entry',
            sa.Column('mt_trans_of_id', sa.Integer, sa.ForeignKey(
                'langstring_entry.id', ondelete='CASCADE', onupdate='CASCADE')))

        op.execute('''UPDATE locale_label
            SET named_locale = (SELECT code FROM locale
                                WHERE locale.id = locale_label.named_locale_id),
                locale_of_label = (SELECT code FROM locale
                                WHERE locale.id = locale_label.locale_id_of_label)''')
        op.execute('''UPDATE user_language_preference
            SET translate = (SELECT code FROM locale
                                WHERE locale.id = user_language_preference.translate_to),
                locale = (SELECT code FROM locale
                                WHERE locale.id = user_language_preference.locale_id)''')
        op.execute('''UPDATE langstring_entry
            SET locale = (
                SELECT CASE WHEN position('-x-mtfrom-' in code) > 1 THEN substring(code for position('-x-mtfrom-' IN code)-1) ELSE code END
                FROM locale WHERE locale.id = langstring_entry.locale_id)''')

        # try finding the precise entry
        op.execute('''UPDATE langstring_entry AS le
            SET mt_trans_of_id = (
                SELECT orig.id FROM langstring_entry AS orig WHERE orig.langstring_id = le.langstring_id
                AND orig.locale = (
                    SELECT substring(code from position('-x-mtfrom-' in code)+10)
                    FROM locale WHERE locale.id = le.locale_id)
                LIMIT 1
            )
            WHERE (SELECT position('-x-mtfrom-' in locale.code) > 1
                    FROM locale WHERE locale.id = le.locale_id) ''')

        # Step 2: Fallback to non-translated entry
        op.execute('''UPDATE langstring_entry AS le
            SET mt_trans_of_id = (
                SELECT orig.id FROM langstring_entry AS orig
                JOIN locale ON (locale.id = orig.locale_id)
                WHERE orig.langstring_id = le.langstring_id
                AND position('-x-mtfrom-' in locale.code) = 0
                LIMIT 1
            )
            WHERE (SELECT position('-x-mtfrom-' in locale.code) > 1
                    FROM locale WHERE locale.id = le.locale_id)
                 AND mt_trans_of_id IS NULL''')

        op.alter_column('locale_label', 'named_locale', nullable=False)
        op.alter_column('locale_label', 'locale_of_label', nullable=False)
        op.alter_column('langstring_entry', 'locale', nullable=False)
        op.alter_column('user_language_preference', 'locale', nullable=False)

        op.drop_constraint(
            'langstring_entry_langstring_id_locale_id_tombstone_date_key',
            'langstring_entry')
        op.drop_constraint(
            'user_language_preference_user_id_locale_id_source_of_eviden_key',
            'user_language_preference')
        op.drop_constraint(
            'locale_label_named_locale_id_locale_id_of_label_key',
            'locale_label')

        op.create_unique_constraint(
            'langstring_entry_langstring_id_locale_tombstone_date_key',
            'langstring_entry', ['langstring_id', 'locale', 'tombstone_date'])
        op.create_unique_constraint(
            'user_language_preference_user_id_locale_source_of_evidence_key',
            'user_language_preference', ['user_id', 'locale', 'source_of_evidence'])
        op.create_unique_constraint(
            'locale_label_named_locale_locale_of_label_key',
            'locale_label', ['named_locale', 'locale_of_label'])

        op.drop_column('locale_label', 'named_locale_id')
        op.drop_column('locale_label', 'locale_id_of_label')
        op.drop_column('user_language_preference', 'locale_id')
        op.drop_column('user_language_preference', 'translate_to')
        op.drop_column('langstring_entry', 'locale_id')
        op.drop_table('locale')


def downgrade(pyramid_env):
    from assembl.lib.sqla import get_session_maker
    db = get_session_maker()()
    with transaction.manager:
        locales = {x for (x,) in db.execute('''
            SELECT DISTINCT named_locale FROM locale_label
            UNION SELECT DISTINCT locale_of_label FROM locale_label
            UNION SELECT DISTINCT locale FROM langstring_entry
            UNION SELECT DISTINCT locale FROM user_language_preference
            UNION SELECT DISTINCT translate FROM user_language_preference
            ''')}
        locales.update({'und', 'mul', 'zxx'})
        locales.remove(None)
        locales.update({'-x-mtfrom-'.join(p) for p in db.execute(
            '''SELECT DISTINCT dest.locale, source.locale
            FROM langstring_entry as source
            JOIN langstring_entry as dest ON (dest.mt_trans_of_id = source.id)''')})

    with context.begin_transaction():
        op.create_table(
            'locale',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('code', sa.String(32), unique=True),
            sa.Column('rtl', sa.Boolean, server_default="0"))

        op.add_column(
            'locale_label', sa.Column(
                'named_locale_id', sa.Integer, sa.ForeignKey(
                    'locale.id', ondelete="CASCADE", onupdate="CASCADE"),
                index=True))
        op.add_column(
            'locale_label', sa.Column(
                'locale_id_of_label', sa.Integer, sa.ForeignKey(
                    'locale.id', ondelete="CASCADE", onupdate="CASCADE"),
                index=True))

        op.add_column(
            'langstring_entry', sa.Column(
                'locale_id', sa.Integer, sa.ForeignKey(
                    'locale.id', ondelete="CASCADE", onupdate="CASCADE"),
                index=True))

        op.add_column(
            'user_language_preference', sa.Column(
                'locale_id', sa.Integer, sa.ForeignKey(
                    'locale.id',ondelete='CASCADE', onupdate='CASCADE'),
                index=False))
        op.add_column(
            'user_language_preference', sa.Column(
                'translate_to', sa.Integer, sa.ForeignKey(
                    'locale.id', onupdate='CASCADE', ondelete='CASCADE')))


        op.execute('INSERT INTO locale (code, rtl) values '
                + ','.join(["('%s', %s)" % (loc, str(is_rtl(loc)).lower())
                           for loc in locales]))

        op.execute('''UPDATE locale_label
            SET named_locale_id = (SELECT id FROM locale
                                WHERE locale.code = locale_label.named_locale),
                locale_id_of_label = (SELECT id FROM locale
                                WHERE locale.code = locale_label.locale_of_label)''')

        op.execute('''UPDATE user_language_preference
            SET locale_id = (SELECT id FROM locale
                                WHERE locale.code = user_language_preference.locale)''')

        op.execute('''UPDATE user_language_preference
            SET translate_to = (SELECT id FROM locale
                                WHERE locale.code = user_language_preference.translate)
            WHERE translate IS NOT NULL''')

        op.execute('''UPDATE langstring_entry
            SET locale_id = (SELECT id FROM locale
                                WHERE locale.code = langstring_entry.locale)
            WHERE mt_trans_of_id IS NULL''')

        op.execute('''UPDATE langstring_entry AS le
            SET locale_id = (SELECT locale.id FROM locale
                WHERE locale.code = concat(le.locale, '-x-mtfrom-',
                (SELECT orig.locale FROM langstring_entry AS orig WHERE orig.id = le.mt_trans_of_id)))
            WHERE le.mt_trans_of_id IS NOT NULL''')

        op.alter_column('locale_label', 'named_locale_id', nullable=False)
        op.alter_column('locale_label', 'locale_id_of_label', nullable=False)
        op.alter_column('user_language_preference', 'locale_id', nullable=False)
        op.alter_column('langstring_entry', 'locale_id', nullable=False)

        op.drop_constraint(
            'langstring_entry_langstring_id_locale_tombstone_date_key',
            'langstring_entry')
        op.drop_constraint(
            'user_language_preference_user_id_locale_source_of_evidence_key',
            'user_language_preference')
        op.drop_constraint(
            'locale_label_named_locale_locale_of_label_key',
            'locale_label')

        op.create_unique_constraint(
            'langstring_entry_langstring_id_locale_id_tombstone_date_key',
            'langstring_entry', ['langstring_id', 'locale_id', 'tombstone_date'])
        op.create_unique_constraint(
            'user_language_preference_user_id_locale_id_source_of_eviden_key',
            'user_language_preference', ['user_id', 'locale_id', 'source_of_evidence'])
        op.create_unique_constraint(
            'locale_label_named_locale_id_locale_id_of_label_key',
            'locale_label', ['named_locale_id', 'locale_id_of_label'])

        op.drop_column('locale_label', 'named_locale')
        op.drop_column('locale_label', 'locale_of_label')
        op.drop_column('langstring_entry', 'locale')
        op.drop_column('user_language_preference', 'locale')
        op.drop_column('user_language_preference', 'translate')
        op.drop_column('langstring_entry', 'mt_trans_of_id')
