import email
from email.header import decode_header as decode_email_header
from datetime import datetime
from time import mktime
from imaplib import IMAP4_SSL, IMAP4
from sqlalchemy.orm import relationship, backref

from sqlalchemy import (
    Column, 
    Boolean,
    Integer, 
    String, 
    Unicode, 
    UnicodeText, 
    DateTime,
    ForeignKey,
    desc
)

from ..db.models import Model
from ..synthesis.models import TableOfContents



class Source(Model):
    """
    A Discussion Source is where commentary that is handled in the form of
    Assembl posts comes from. 

    A discussion source should have a method for importing all content, as well
    as only importing new content. Maybe the standard interface for this should
    be `source.import()`.
    """
    __tablename__ = "source"

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(60), nullable=False)
    type = Column(String(60), nullable=False)

    creation_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_import = Column(DateTime)

    table_of_contents_id = Column(Integer, ForeignKey(
        'table_of_contents.id', 
        ondelete='CASCADE'
    ))

    table_of_contents = relationship(
        "TableOfContents", 
        backref=backref('sources', order_by=creation_date)
    )

    __mapper_args__ = {
        'polymorphic_identity': 'source',
        'polymorphic_on': type
    }

    def __repr__(self):
        return "<Source '%s'>" % self.name


class Content(Model):
    """
    Content is a polymorphic class to describe what is imported from a Source.
    """
    __tablename__ = "content"

    id = Column(Integer, primary_key=True)
    type = Column(String(60), nullable=False)
    
    import_date = Column(DateTime, default=datetime.utcnow)

    source_id = Column(Integer, ForeignKey('source.id', ondelete='CASCADE'))
    source = relationship(
        "Source",
        backref=backref('contents', order_by=import_date)
    )

    post = relationship("Post", uselist=False)

    __mapper_args__ = {
        'polymorphic_identity': 'content',
        'polymorphic_on': 'type'
    }

    def make_post(self):
        self.post = self.post or Post(content=self)

    def __repr__(self):
        return "<Content '%s'>" % self.type


class Mailbox(Source):
    """
    A Mailbox refers to an Email inbox that can be accessed with IMAP, and
    whose messages should be imported and displayed as Posts.
    """
    __tablename__ = "mailbox"

    id = Column(Integer, ForeignKey(
        'source.id', 
        ondelete='CASCADE'
    ), primary_key=True)

    host = Column(Unicode(1024), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(Unicode(1024), nullable=False)
    use_ssl = Column(Boolean, default=True)
    password = Column(Unicode(1024), nullable=False)
    mailbox = Column(Unicode(1024), default=u"INBOX", nullable=False)

    last_imported_email_uid = Column(Unicode(255))

    __mapper_args__ = {
        'polymorphic_identity': 'mailbox',
    }

    def import_content(self, only_new=False):
        if self.use_ssl:
            mailbox = IMAP4_SSL(host=self.host, port=self.port)
        else:
            mailbox = IMAP4(host=self.host, port=self.port)

        mailbox.login(self.username, self.password)
        mailbox.select(self.mailbox)

        command = "ALL"

        if only_new and self.last_imported_email_uid:
            command = "(UID %s:*)" % self.last_imported_email_uid
        
        search_status, search_result = mailbox.uid('search', None, command)

        email_ids = search_result[0].split()

        if only_new:
            # discard the first message, it should be the last imported email.
            del email_ids[0]
        
        def import_email(email_id):
            status, message_data = mailbox.fetch(email_id, "(RFC822)")

            for response_part in message_data:
                if isinstance(response_part, tuple):
                    message_string = response_part[1]

            parsed_email = email.message_from_string(message_string)

            body = None
            
            if parsed_email.is_multipart():
                for part in parsed_email.get_payload():
                    if part['Content-Type'].split(';')[0] == 'text/plain':
                        body = part.get_payload()
            else:
                body = parsed_email.get_payload()

            def email_header_to_unicode(header_string):
                decoded_header = decode_email_header(header_string);
                default_charset = 'ASCII'
                
                text = ''.join(
                    [ 
                        unicode(t[0], t[1] or default_charset) for t in \
                        decoded_header 
                    ]
                )

                return text

            new_message_id = parsed_email.get('Message-ID', None)
            if new_message_id: new_message_id = email_header_to_unicode(
                new_message_id
            )

            new_in_reply_to = parsed_email.get('In-Reply-To', None)
            if new_in_reply_to: new_in_reply_to = email_header_to_unicode(
                new_in_reply_to
            )

            new_email = Email(
                to_address=email_header_to_unicode(parsed_email['To']),
                from_address=email_header_to_unicode(parsed_email['From']),
                subject=email_header_to_unicode(parsed_email['Subject']),
                send_date=datetime.utcfromtimestamp(
                    mktime(
                        email.utils.parsedate(
                            parsed_email['Date']
                        )
                    )
                ),
                message_id=new_message_id,
                in_reply_to=new_in_reply_to,
                body=body.strip().decode('ISO-8859-1'),
                full_message=str(parsed_email).decode('ISO-8859-1')
            )

            return new_email

        if len(email_ids):
            new_emails = map(import_email, email_ids)

            self.last_imported_email_uid = \
                email_ids[len(email_ids)-1]

            self.contents.extend(new_emails)

        self.last_import = datetime.utcnow()

    def __repr__(self):
        return "<Mailbox '%s'>" % self.name


class Email(Content):
    """
    An Email refers to an email message that was imported from an Mailbox.
    """
    __tablename__ = "email"

    id = Column(Integer, ForeignKey(
        'content.id', 
        ondelete='CASCADE'
    ), primary_key=True)

    to_address = Column(Unicode(1024), nullable=False)
    from_address = Column(Unicode(1024), nullable=False)
    subject = Column(Unicode(1024), nullable=False)
    body = Column(UnicodeText)

    full_message = Column(UnicodeText)

    message_id = Column(Unicode(255))
    in_reply_to = Column(Unicode(255))

    send_date = Column(DateTime, nullable=False)
    import_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    __mapper_args__ = {
        'polymorphic_identity': 'email',
    }

    def make_post(self):
        super(Email, self).make_post()

        # if there is an email.in_reply_to, search posts with content.type
        # == email and email.message_id == email.in_reply_to, then set that
        # email's post's id as the parent of this new post.

        # search for emails where the in_reply_to is the same as the
        # message_id for this email, then set their post's parent to the
        # id of this new post.

    def __repr__(self):
        return "<Email '%s to %s'>" % (
            self.from_address.encode('utf-8'), 
            self.to_address.encode('utf-8')
        )


class Post(Model):
    """
    A Post represents input into the broader discussion taking place on
    Assembl. It may be a response to another post, it may have responses, and
    its content may be of any type.
    """
    __tablename__ = "post"

    id = Column(Integer, primary_key=True)
    creation_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    parent_id = Column(Integer, ForeignKey('post.id'))
    children = relationship(
        "Post",
        backref=backref('parent'),
        remote_side=[id],
        order_by=desc(creation_date)
    )

    content_id = Column(Integer, ForeignKey('content.id', ondelete='CASCADE'))
    content = relationship('Content', uselist=False)

    def __repr__(self):
        return "<Post '%s'>" % self.content
