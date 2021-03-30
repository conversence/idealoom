# coding=UTF-8
""":py:class:`assembl.models.post.Post` that came as email, and utility code for handling email."""
from builtins import str
from builtins import object
import email
import mailbox
import re
import smtplib
import os
from html import escape as html_escape
from collections import defaultdict
from email.header import decode_header as decode_email_header, Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr, mktime_tz, parsedate_tz
from email.message import Message
import logging
from html import escape

from future.utils import native_str, as_native_str, binary_type, PY2, bytes_to_native_str
from past.builtins import str as oldstr
import jwzthreading
from ..lib.clean_input import sanitize_html
from pyramid.threadlocal import get_current_registry
from datetime import datetime
# from imaplib2 import IMAP4_SSL, IMAP4
import transaction
from pyisemail import is_email
from sqlalchemy.orm import (deferred, undefer, joinedload_all)
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    String,
    Binary,
    UnicodeText,
    Boolean,
)
from ..lib.sqla_types import (CoerceUnicode, EmailString)

from .langstrings import LangString
from .generic import PostSource
from .post import ImportedPost
from .auth import EmailAccount
from .attachment import File, PostAttachment, AttachmentPurpose
from ..tasks.imap import import_mails
from ..tasks.translate import translate_content


log = logging.getLogger(__name__)


class AbstractMailbox(PostSource):
    """
    A Mailbox refers to any source of Email, and
    whose messages should be imported and displayed as Posts.
    It must not be instanciated directly
    """
    __tablename__ = "mailbox"
    id = Column(Integer, ForeignKey(
        'post_source.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    folder = Column(UnicodeText, default=u"INBOX", nullable=False)

    # The admin sender email is used for notifications, usually with the
    # name of the original post sender.
    admin_sender = Column(EmailString)

    last_imported_email_uid = Column(UnicodeText)
    subject_mangling_regex = Column(UnicodeText, nullable=True)
    subject_mangling_replacement = Column(UnicodeText, nullable=True)
    __compiled_subject_mangling_regex = None

    def _compile_subject_mangling_regex(self):
        if(self.subject_mangling_regex):
            self.__compiled_subject_mangling_regex =\
                re.compile(self.subject_mangling_regex)
        else:
            self.__compiled_subject_mangling_regex = None

    __mapper_args__ = {
        'polymorphic_identity': 'mailbox',
        'with_polymorphic': '*'
    }

    def mangle_mail_subject(self, subject):
        if self.__compiled_subject_mangling_regex is None:
            self._compile_subject_mangling_regex()

        if not self.__compiled_subject_mangling_regex:
            return subject
        if self.subject_mangling_replacement:
            repl = self.subject_mangling_replacement
        else:
            repl = ''
        (retval, num) =\
            self.__compiled_subject_mangling_regex.subn(repl, subject)
        return retval

    @staticmethod
    def clean_angle_brackets(message_id):
        if message_id and message_id.startswith("<") and message_id.endswith(">"):
            return message_id[1:-1]
        return message_id

    @staticmethod
    def text_to_html(message_body):
        return "<pre>%s</pre>" % escape(message_body)

    @staticmethod
    def strip_full_message_quoting_plaintext(message_body):
        """Assumes any encoding conversions have already been done
        """
        #Most useful to develop this:
        #http://www.motobit.com/util/quoted-printable-decoder.asp
        debug = False;
        #To be considered matching, each line must match successive lines, in order
        quote_announcement_lines_regexes = {
            'generic_original_message':  {
                        'announceLinesRegexes': [re.compile("/-+\s*Original Message\s*-+/")],
                        'quotePrefixRegex': re.compile(r"^>\s|^>$")
                    },
            'gmail_fr_circa_2012':  {
                        'announceLinesRegexes': [re.compile(r"^Le .*, .*<.*@.*> a écrit :")],# 2012 Le 6 juin 2011 15:43, <nicolas.decordes@orange-ftgroup.com> a écrit :
                        'quotePrefixRegex': re.compile(r"^>\s|^>$")
                    },
            'gmail_en_circa_2014':  {
                        'announceLinesRegexes': [re.compile(r"^\d{4}-\d{2}-\d{2}.*<.*@.*>:")],# 2014-06-17 10:32 GMT-04:00 Benoit Grégoire <benoitg@coeus.ca>:
                        'quotePrefixRegex': re.compile(r"^>\s|^>$")
                    },
            'outlook_fr_circa_2012':  {
                        'announceLinesRegexes': [re.compile(r"^\d{4}-\d{2}-\d{2}.*<.*@.*>:")],# 2014-06-17 10:32 GMT-04:00 Benoit Grégoire <benoitg@coeus.ca>:
                        'quotePrefixRegex': re.compile(r"^>\s|^>$")
                    },
            'outlook_fr_multiline_circa_2012': {
                        'announceLinesRegexes': [re.compile(r"^_+$"), #________________________________
                                                re.compile(r"^\s*$"), #Only whitespace
                                                re.compile(r"^De :.*$"),
                                                re.compile(r"^Envoy.+ :.*$"),
                                                re.compile(r"^À :.*$"),
                                                re.compile(r"^Objet :.*$"),
                                                ],
                        'quotePrefixRegex': re.compile(r"^.*$")
                    },
            'outlook_en_multiline_circa_2012': {
                        'announceLinesRegexes': [re.compile(r"^_+$"), #________________________________
                                                re.compile(r"^\s*$"), #Only whitespace
                                                re.compile(r"^From:.*$"),
                                                re.compile(r"^Sent:.*$"),
                                                re.compile(r"^To:.*$"),
                                                re.compile(r"^Subject:.*$"),
                                                ],
                        'quotePrefixRegex': re.compile(r"^.*$")
                    },
            }
        def check_quote_announcement_lines_match(currentQuoteAnnounce, keysStillMatching, lineToMatch):

            if len(keysStillMatching) == 0:
                #Restart from scratch
                keysStillMatching = list(quote_announcement_lines_regexes.keys())
            nextIndexToMatch = len(currentQuoteAnnounce)
            keys = list(keysStillMatching)
            matchComplete = False
            for key in keys:
                if len(quote_announcement_lines_regexes[key]['announceLinesRegexes']) > nextIndexToMatch:
                    if quote_announcement_lines_regexes[key]['announceLinesRegexes'][nextIndexToMatch].match(lineToMatch):
                        if len(quote_announcement_lines_regexes[key]['announceLinesRegexes']) -1 == nextIndexToMatch:
                            matchComplete = key
                    else:
                        keysStillMatching.remove(key)
            if len(keysStillMatching)>0:
                currentQuoteAnnounce.append(lineToMatch)
            return matchComplete, keysStillMatching


        defaultQuotePrefixRegex=re.compile(r"^>\s|^>$")
        quote_prefix_regex=defaultQuotePrefixRegex
        whitespace_line_regex=re.compile(r"^\s*$")
        retval = []
        currentQuoteAnnounce = []
        keysStillMatching = []
        currentQuote = []
        currentWhiteSpace = []
        class LineState(object):
            Normal="Normal"
            PrefixedQuote='PrefixedQuote'
            PotentialQuoteAnnounce='PotentialQuoteAnnounce'
            QuoteAnnounceLastLine='QuoteAnnounceLastLine'
            AllWhiteSpace='AllWhiteSpace'

        line_state_before_transition = LineState.Normal
        previous_line_state = LineState.Normal
        line_state = LineState.Normal
        for line in message_body.splitlines():
            if line_state != previous_line_state:
                line_state_before_transition = previous_line_state
            previous_line_state = line_state

            (matchComplete, keysStillMatching) = check_quote_announcement_lines_match(currentQuoteAnnounce, keysStillMatching, line)
            if matchComplete:
                line_state = LineState.QuoteAnnounceLastLine
                quote_prefix_regex = quote_announcement_lines_regexes[keysStillMatching[0]]['quotePrefixRegex']
            elif len(keysStillMatching) > 0:
                line_state = LineState.PotentialQuoteAnnounce
            elif quote_prefix_regex.match(line):
                line_state = LineState.PrefixedQuote
            elif whitespace_line_regex.match(line):
                line_state = LineState.AllWhiteSpace
            else:
                line_state = LineState.Normal
            if line_state == LineState.Normal:
                if((previous_line_state != LineState.AllWhiteSpace) & len(currentWhiteSpace) > 0):
                    retval += currentWhiteSpace
                    currentWhiteSpace = []
                if(len(currentQuote) > 0):
                    retval += currentQuoteAnnounce
                    retval += currentQuote
                    currentQuote = []
                    currentQuoteAnnounce = []
                if(previous_line_state == LineState.AllWhiteSpace):
                    retval += currentWhiteSpace
                    currentWhiteSpace = []
                retval.append(line)
            elif line_state == LineState.PrefixedQuote:
                currentQuote.append(line)
            elif line_state == LineState.QuoteAnnounceLastLine:
                currentQuoteAnnounce = []
            elif line_state == LineState.AllWhiteSpace:
                currentWhiteSpace.append(line)
            log.debug("%-30s %s" % (line_state, line))
        #if line_state == LineState.PrefixedQuote | (line_state == LineState.AllWhiteSpace & line_state_before_transition == LineState.PrefixedQuote)
            #We just let trailing quotes and whitespace die...
        return '\n'.join(retval)

    @staticmethod
    def strip_full_message_quoting_html(message_body):
        """Assumes any encoding conversions have already been done
        """
        #Most useful to develop this:
        #http://www.motobit.com/util/quoted-printable-decoder.asp
        #http://www.freeformatter.com/html-formatter.html
        #http://www.freeformatter.com/xpath-tester.html#ad-output

        debug = True;
        from lxml import html, etree

        doc = None
        try:
            doc = html.fromstring(message_body)
        except etree.ParserError: # If the parsed HTML document is empty, we get a "ParserError: Document is empty" exception. So the stripped message we return is an empty string (if we keep the exception it blocks the SourceReader)
            return ""

        #Strip GMail quotes
        matches = doc.find_class('gmail_quote')
        if len(matches) > 0 and (
            not matches[0].text
            or "---------- Forwarded message ----------" not in matches[0].text
        ):
            matches[0].drop_tree()
            return html.tostring(doc, encoding="unicode")

        #Strip modern Apple Mail quotes
        find = etree.XPath(r"//child::blockquote[contains(@type,'cite')]/preceding-sibling::br[contains(@class,'Apple-interchange-newline')]/parent::node()/parent::node()")
        matches = find(doc)
        #log.debug(len(matches))
        #for index,match in enumerate(matches):
        #    log.debug("Match: %d: %s " % (index, html.tostring(match, encoding="unicode")))
        if len(matches) == 1:
            matches[0].drop_tree()
            return html.tostring(doc, encoding="unicode")


        #Strip old AppleMail quotes (french)
        regexpNS = "http://exslt.org/regular-expressions"
        ##Trying to match:  Le 6 juin 2011 à 11:02, Jean-Michel Cornu a écrit :
        find = etree.XPath(r"//child::div[re:test(text(), '^.*Le .*\d{4} .*:\d{2}, .* a .*crit :.*$', 'i')]/following-sibling::br[contains(@class,'Apple-interchange-newline')]/parent::node()",
                    namespaces={'re': regexpNS})
        matches = find(doc)
        if len(matches) == 1:
            matches[0].drop_tree()
            return html.tostring(doc, encoding="unicode")

        #Strip Outlook quotes (when outlook gives usable structure)
        find = etree.XPath(r"//body/child::blockquote/child::div[contains(@class,'OutlookMessageHeader')]/parent::node()")
        matches = find(doc)
        if len(matches) == 1:
            matches[0].drop_tree()
            return html.tostring(doc, encoding="unicode")

        #Strip Outlook quotes (when outlook gives NO usable structure)
        successiveStringsToMatch = [
                                        '|'.join(['^From:.*$','^De :.*$']),
                                        '|'.join(['^Sent:.*$','^Envoy.+ :.*$']),
                                        '|'.join(['^To:.*$','^.+:.*$']), #Trying to match À, but unicode is really problematic in lxml regex
                                        '|'.join(['^Subject:.*$','^Objet :.*$']),
                                    ]
        regexpNS = "http://exslt.org/regular-expressions"
        successiveStringsToMatchRegex = [
            r"descendant::*[re:test(text(), '" + singleHeaderLanguageRegex + "')]"
            for singleHeaderLanguageRegex in successiveStringsToMatch
        ]

        regex = " and ".join(successiveStringsToMatchRegex)
        find = etree.XPath(r"//descendant::div["+regex+"]",
                            namespaces={'re':regexpNS})
        matches = find(doc)
        if len(matches) == 1:
            findQuoteBody = etree.XPath(r"//descendant::div["+regex+"]/following-sibling::*",
                            namespaces={'re':regexpNS})
            quoteBodyElements = findQuoteBody(doc)
            for quoteElement in quoteBodyElements:
                #This moves the text to the tail of matches[0]
                quoteElement.drop_tree()
            matches[0].tail = None
            matches[0].drop_tree()
            return html.tostring(doc, encoding="unicode")

        #Strip Thunderbird quotes
        mainXpathFragment = "//child::blockquote[contains(@type,'cite') and boolean(@cite)]"
        find = etree.XPath(mainXpathFragment+"/self::blockquote")
        matches = find(doc)
        if len(matches) == 1:
            matchQuoteAnnounce = doc.xpath(mainXpathFragment+"/preceding-sibling::*")
            if len(matchQuoteAnnounce) > 0:
                matchQuoteAnnounce[-1].tail = None
                matches[0].drop_tree()
                return html.tostring(doc, encoding="unicode")

        #Nothing was stripped...
        return html.tostring(doc, encoding="unicode")

    def parse_email(self, message_string, existing_email=None):
        """ Creates or replace a email from a string """
        if isinstance(message_string, binary_type):
            message_bytes = message_string
            message_string = message_bytes.decode('utf-8')
        else:
            message_bytes = message_string.encode('utf-8')
        parsed_email = email.message_from_string(
            bytes_to_native_str(message_bytes))
        body = None
        error_description = None
        default_charset = parsed_email.get_charset() or 'ISO-8859-1'

        def extract_text(part):
            """ Returns HTML or Text parts of a message"""
            mimetype = part.get_content_type()
            if part.is_multipart():
                if mimetype == "multipart/alternative":
                    text_part = None
                    for subpart in part.get_payload():
                        (subpart_c, subtype) = extract_text(subpart)
                        if subpart_c is None:
                            continue
                        elif subtype == "text/html":
                            return (subpart_c, subtype)
                        elif subtype == "text/plain":
                            text_part = subpart_c
                        else:
                            log.debug("cannot treat alternative %s", subtype)
                    if text_part:
                        return (text_part, "text/plain")
                    return (None, None)
                else:
                    parts = []
                    parts_type = None
                    for subpart in part.get_payload():
                        (subpart_c, subtype) = extract_text(subpart)
                        if not subpart_c:
                            continue
                        elif subtype == 'text/html':
                            if parts_type == 'text/plain':
                                parts = [AbstractMailbox.text_to_html(p)
                                         for p in parts]
                            parts_type = 'text/html'
                            parts.append(subpart_c)
                        elif subtype == 'text/plain':
                            if parts_type == 'text/html':
                                subpart_c = AbstractMailbox.text_to_html(subpart_c)
                            else:
                                parts_type = 'text/plain'
                            parts.append(subpart_c)
                        elif not subpart.is_attachment():
                            log.debug("cannot treat text subpart %s", subtype)
                    if not parts:
                        return (None, None)
                    if len(parts) == 1:
                        return (parts[0], parts_type)
                    if parts_type == "text/html":
                        return "\n".join("<div>%s</div>" % p for p in parts), parts_type
                    elif parts_type == "text/plain":
                        return ("\n".join(parts), parts_type)
            elif part.get_content_disposition():
                # TODO: Inline attachments
                return (None, None)
            elif mimetype in ("text/html", "text/plain"):
                charset = part.get_content_charset(default_charset)
                decoded_part = part.get_payload(decode=True)
                decoded_part = decoded_part.decode(charset, 'replace')
                if mimetype == "text/html":
                    decoded_part = sanitize_html(
                        AbstractMailbox.strip_full_message_quoting_html(
                            decoded_part))
                else:
                    decoded_part = AbstractMailbox.strip_full_message_quoting_plaintext(
                        decoded_part)
                return (decoded_part, mimetype)
            else:
                log.debug("cannot treat part %s", mimetype)
                return (None, None)

        (body, mimeType) = extract_text(parsed_email)

        def email_header_to_unicode(header_string, join_crlf=True):
            text = u''.join(
                txt.decode(enc)
                if enc
                else txt.decode('iso-8859-1')
                if isinstance(txt, bytes)
                else txt
                for (txt, enc) in decode_email_header(header_string)
            )

            if join_crlf:
                text = u''.join(text.split(u'\r\n'))

            return text

        new_message_id = parsed_email.get('Message-ID', None)
        if new_message_id:
            new_message_id = self.clean_angle_brackets(
                email_header_to_unicode(new_message_id))
        else:
            error_description = "Unable to parse the Message-ID for message string: \n%s" % message_string
            return (None, None, error_description)

        assert new_message_id

        new_in_reply_to = parsed_email.get('In-Reply-To', None)
        if new_in_reply_to:
            new_in_reply_to = self.clean_angle_brackets(
                email_header_to_unicode(new_in_reply_to))

        sender_name, sender_email = parseaddr(parsed_email.get('From'))
        sender_name = email_header_to_unicode(sender_name)
        if sender_name:
            sender = "%s <%s>" % (sender_name, sender_email)
        else:
            sender = sender_email
        sender_email_account = EmailAccount.get_or_make_profile(self.db, sender_email, sender_name)
        creation_date = datetime.utcfromtimestamp(
            mktime_tz(parsedate_tz(parsed_email['Date'])))
        subject = email_header_to_unicode(parsed_email['Subject'], False)
        recipients = email_header_to_unicode(parsed_email['To'])
        body = body.strip()
        # Try/except for a normal situation is an anti-pattern,
        # but sqlalchemy doesn't have a function that returns
        # 0, 1 result or an exception
        try:
            email_object = self.db.query(Email).filter(
                Email.source_post_id == new_message_id,
                Email.discussion_id == self.discussion_id,
                Email.source == self
            ).one()
            if existing_email and existing_email != email_object:
                raise ValueError("The existing object isn't the same as the one found by message id")
            email_object.recipients = recipients
            email_object.sender = sender
            email_object.creation_date = creation_date
            email_object.source_post_id = new_message_id
            email_object.in_reply_to = new_in_reply_to
            email_object.body_mime_type = mimeType
            email_object.imported_blob = message_bytes
            # TODO MAP: Make this nilpotent.
            email_object.subject = LangString.create(subject)
            email_object.body = LangString.create(body)
        except NoResultFound:
            email_object = Email(
                discussion=self.discussion,
                source=self,
                recipients=recipients,
                sender=sender,
                subject=LangString.create(subject),
                creation_date=creation_date,
                source_post_id=new_message_id,
                in_reply_to=new_in_reply_to,
                body=LangString.create(body),
                body_mime_type = mimeType,
                imported_blob=message_bytes
            )

        except MultipleResultsFound:
            """ TO find duplicates (this should no longer happen, but in case it ever does...

SELECT * FROM post WHERE id in (SELECT MAX(post.id) as max_post_id FROM imported_post JOIN post ON (post.id=imported_post.id) GROUP BY message_id, source_id HAVING COUNT(post.id)>1)

To kill them:


USE assembl;
UPDATE  post p
SET     parent_id = (
SELECT new_post_parent.id AS new_post_parent_id
FROM post AS post_to_correct
JOIN post AS bad_post_parent ON (post_to_correct.parent_id = bad_post_parent.id)
JOIN post AS new_post_parent ON (new_post_parent.message_id = bad_post_parent.message_id AND new_post_parent.id <> bad_post_parent.id)
WHERE post_to_correct.parent_id IN (
  SELECT MAX(post.id) as max_post_id
  FROM imported_post
  JOIN post ON (post.id=imported_post.id)
  GROUP BY message_id, source_id
  HAVING COUNT(post.id)>1
  )
AND p.id = post_to_correct.id
)

USE assembl;
DELETE
FROM post WHERE post.id IN (SELECT MAX(post.id) as max_post_id FROM imported_post JOIN post ON (post.id=imported_post.id) GROUP BY message_id, source_id HAVING COUNT(post.id)>1)

"""
            raise MultipleResultsFound("ID %s has duplicates in source %d" % (
                new_message_id, self.id))
        email_object.creator = sender_email_account.profile
        # email_object = self.db.merge(email_object)

        if not email_object.attachments:
            attachment_parts = [p for p in parsed_email.walk()
                                if p.get_content_disposition()]
            for (num, part) in enumerate(attachment_parts):
                title = part.get_filename("file %d" % num)
                doc = File(
                    discussion=self.discussion,
                    mime_type=part.get_content_type(),
                    title=title)
                payload = part.get_payload(decode=True)
                if part.get_content_type() == "message/rfc822":
                    payload = part.as_bytes()
                doc.add_raw_data(payload)
                attachment = PostAttachment(
                    discussion=self.discussion,
                    document=doc,
                    post=email_object,
                    # the following should reflect whether part.get_content_disposition()
                    # is inline or attachment
                    attachmentPurpose='EMBED_ATTACHMENT',
                    creator=email_object.creator,
                    title=title)
                self.db.add(attachment)

        email_object.guess_languages()
        return (email_object, parsed_email, error_description)

    @staticmethod
    def guess_encoding(blob):
        """Blobs should be ascii, but sometimes are multiply-encoded
        utf-8, probably a bug of the underlying library.
        Temporary patch until it is fixed."""
        if not isinstance(blob, native_str):
            try:
                # shortcut that will work in 99% of cases
                return blob.decode('ascii')
            except UnicodeDecodeError:
                blob = blob.decode('iso-8859-1')
        while True:
            try:
                blob2 = blob.encode('iso-8859-1').decode('utf-8')
                if blob == blob2:
                    return blob
                blob = blob2
            except (UnicodeDecodeError, UnicodeEncodeError):
                return blob

    """
    emails have to be a complete set
    """
    @staticmethod
    def thread_mails(emails):
        #log.debug('Threading...')
        emails_for_threading = []
        for mail in emails:
            blob = AbstractMailbox.guess_encoding(mail.imported_blob)
            email_for_threading = jwzthreading.Message(email.message_from_string(blob))
            #Store our emailsubject, jwzthreading does not decode subject itself
            email_for_threading.subject = mail.subject.first_original().value
            #Store our email object pointer instead of the raw message text
            email_for_threading.message = mail
            emails_for_threading.append(email_for_threading)

        threaded_emails = jwzthreading.thread(emails_for_threading)

        # Output
        for container in threaded_emails:
            jwzthreading.print_container(container, 0, True)

        def update_threading(threaded_emails, debug=False):
            log.debug("\n\nEntering update_threading() for %ld mails:" % len(threaded_emails))
            for container in threaded_emails:
                message = container['message']
                # if debug:
                    #jwzthreading.print_container(container)
                message_string = "%s %s %d " % (
                    message.subject, message.message_id,
                    message.message.id) if message else "null "
                log.debug("Processing: %s container: %s parent: %s children :%s" % (
                    message_string, container, container.parent, container.children))

                if(message):
                    current_parent = message.message.parent
                    if(current_parent):
                        db_parent_message_id = current_parent.message_id
                    else:
                        db_parent_message_id = None

                    if container.parent:
                        parent_message = container.parent['message']
                        if parent_message:
                            #jwzthreading strips the <>, re-add them
                            algorithm_parent_message_id = u"<" + parent_message.message_id + u">"
                        else:
                            log.warn("Parent was a dummy container, we may need "
                                     "to handle this case better, as we just "
                                     "potentially lost sibling relationships")
                            algorithm_parent_message_id = None
                    else:
                        algorithm_parent_message_id = None
                    log.debug("Current parent from database: " + repr(db_parent_message_id))
                    log.debug("Current parent from algorithm: " + repr(algorithm_parent_message_id))
                    log.debug("References: " + repr(message.references))
                    if algorithm_parent_message_id != db_parent_message_id:
                        if current_parent == None or isinstance(current_parent, Email):
                            log.debug("UPDATING PARENT for :" + repr(message.message.message_id))
                            new_parent = parent_message.message if algorithm_parent_message_id else None
                            log.debug(repr(new_parent))
                            message.message.set_parent(new_parent)
                        else:
                            log.debug("Skipped reparenting:  the current parent "
                                      "isn't an email, the threading algorithm only "
                                      "considers mails")
                    update_threading(container.children, debug=debug)
                else:
                    log.debug("Current message ID: None, was a dummy container")
                    update_threading(container.children, debug=debug)
        update_threading(threaded_emails, debug=False)

    def reprocess_content(self):
        """ Allows re-parsing all content as if it were imported for the first time
            but without re-hitting the source, or changing the object ids.
            Call when a code change would change the representation in the database
            """
        session = self.db
        emails = session.query(Email.id).filter(
                Email.source_id == self.id)
        for email_id in emails:
            with transaction.manager:
                email_ = Email.get(email_id).options(
                    joinedload_all(Email.parent), undefer(Email.imported_blob))
                blob = AbstractMailbox.guess_encoding(email.imported_blob)
                (email_object, dummy, error) = self.parse_email(blob, email)

        with transaction.manager:
            self.thread_mails(emails)

    def import_content(self, only_new=True):
        from assembl.lib.config import get_config
        from pyramid.settings import asbool
        assert self.id
        config = get_config()
        if asbool(config.get('use_source_reader_for_mail', False)):
            super(AbstractMailbox, self).import_content(only_new)
        else:
            import_mails.delay(self.id, only_new)

    _address_match_re = re.compile(
        r'[\w\-][\w\-\.]+@[\w\-][\w\-\.]+[a-zA-Z]{1,4}'
    )

    def most_common_recipient_address(self):
        """
        Find the most common recipient address of the contents of this emaila
        address. This address can, in most use-cases can be considered the
        mailing list address.
        """

        recipients = self.db.query(
            Email.recipients,
        ).filter(
            Email.source_id == self.id,
        )

        addresses = defaultdict(int)

        for (recipients, ) in recipients:
            for address in self._address_match_re.findall(recipients):
                addresses[address] += 1

        if addresses:
            addresses = list(addresses.items())
            addresses.sort(key=lambda address_count: address_count[1])
            return addresses[-1][0]


    def send_post(self, post):
        #TODO benoitg
        log.warn("TODO: Mail::send_post():  Actually queue message")
        #make sure you have a request and use the pyramid mailer

    def message_ok_to_import(self, message_string):
        """Check if message should be imported at all (not a bounce, vacation,
        etc.)

        The reference is La référence est http://tools.ietf.org/html/rfc3834
        """
        #TODO:  This is a double-parse, refactor parse_message so we can reuse it
        if isinstance(message_string, binary_type):
            message_string = message_string.decode('utf-8')
        parsed_email = email.message_from_string(message_string)
        if parsed_email.get('Return-Path', None) == '<>':
            #TODO:  Check if a report-type=delivery-status; is present,
            # and process the bounce
            return False
        if parsed_email.get('Precedence', None) == 'bulk':
            # Possibly a mailing list message: Allow for mailing lists only
            return isinstance(self, MailingList)
        if parsed_email.get('Precedence', None) == 'list':
            # A mailing list message: Allow for mailing lists only
            return isinstance(self, MailingList)
        return parsed_email.get('Auto-Submitted', None) != 'auto-generated'

    def generate_message_id(self, source_post_id):
        if source_post_id.startswith('<') and source_post_id.endswith('>'):
            source_post_id = source_post_id[1:-1]
        # Use even invalid ids if they come from mail.
        return source_post_id


class IMAPMailbox(AbstractMailbox):
    """
    A IMAPMailbox refers to an Email inbox that can be accessed with IMAP.
    """
    __tablename__ = "source_imapmailbox"
    id = Column(Integer, ForeignKey(
        'mailbox.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    host = Column(String(1024), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(UnicodeText, nullable=False)
    #Note:  If using STARTTLS, this should be set to false
    use_ssl = Column(Boolean, default=True)
    password = Column(UnicodeText, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'source_imapmailbox',
        'with_polymorphic': '*'
    }
    @staticmethod
    def do_import_content(mbox, only_new=True):
        mbox = mbox.db.merge(mbox)
        session = mbox.db
        session.add(mbox)
        if mbox.use_ssl:
            mailbox = IMAP4_SSL(host=mbox.host.encode('utf-8'), port=mbox.port)
        else:
            mailbox = IMAP4(host=mbox.host.encode('utf-8'), port=mbox.port)
        if 'STARTTLS' in mailbox.capabilities:
            #Always use starttls if server supports it
            mailbox.starttls()
        mailbox.login(mbox.username, mbox.password)
        mailbox.select(mbox.folder)

        command = "ALL"
        search_status = None

        email_ids = None
        if only_new and mbox.last_imported_email_uid:
            command = "(UID %s:*)" % mbox.last_imported_email_uid

            search_status, search_result = mailbox.uid('search', None, command)
            #log.debug("UID searched with: "+ command + ", got result "+repr(search_status)+" and found "+repr(search_result))
            email_ids = search_result[0].split()
            #log.debug(email_ids)

        if (only_new and search_status == 'OK' and email_ids
                and email_ids[0] == mbox.last_imported_email_uid):
            # Note:  the email_ids[0]==mbox.last_imported_email_uid test is
            # necessary beacuse according to https://tools.ietf.org/html/rfc3501
            # seq-range like "3291:* includes the UID of the last message in
            # the mailbox, even if that value is less than 3291."

            # discard the first message, it should be the last imported email.
            del email_ids[0]
        else:
            # Either:
            # a) we don't import only new messages or
            # b) the message with mbox.last_imported_email_uid hasn't been found
            #    (may have been deleted)
            # In this case we request all messages and rely on duplicate
            # detection
            command = "ALL"
            search_status, search_result = mailbox.uid('search', None, command)
            # log.debug("UID searched with: "+ command + ", got result "+repr(search_status)+" and found "+repr(search_result))
            assert search_status == 'OK'
            email_ids = search_result[0].split()

        def import_email(mailbox_obj, email_id):
            session = mailbox_obj.db
            #log.debug("running fetch for message: "+email_id)
            status, message_data = mailbox.uid('fetch', email_id, "(RFC822)")
            assert status == 'OK'

            #log.debug(repr(message_data))
            for response_part in message_data:
                if isinstance(response_part, tuple):
                    message_string = response_part[1]
            assert message_string
            if mailbox_obj.message_ok_to_import(message_string):
                (email_object, dummy, error) = mailbox_obj.parse_email(message_string)
                if error:
                    raise Exception(error)
                session.add(email_object)
                translate_content(email_object)  # should delay
            else:
                log.info("Skipped message with imap id %s (bounce or vacation message)"% (email_id))
            #log.debug("Setting mailbox_obj.last_imported_email_uid to "+email_id)
            mailbox_obj.last_imported_email_uid = email_id

        if len(email_ids):
            log.info("Processing messages from IMAP: %d "% (len(email_ids)))
            for email_id in email_ids:
                with transaction.manager:
                    import_email(mbox, email_id)
        else:
            log.info("No IMAP messages to process")

        discussion_id = mbox.discussion_id
        mailbox.close()
        mailbox.logout()

        with transaction.manager:
            if len(email_ids):
                #We imported mails, we need to re-thread
                emails = session.query(Email).filter(
                    Email.discussion_id == discussion_id,
                    ).options(joinedload_all(Email.parent))

                AbstractMailbox.thread_mails(emails)

    def make_reader(self):
        from assembl.tasks.imapclient_source_reader import IMAPReader
        return IMAPReader(self.id)

    def get_send_address(self):
        """
        Get the email address to send a message to the discussion
        """
        return self.most_common_recipient_address()

class MailingList(IMAPMailbox):
    """
    A mailbox with mailing list semantics
    (single post address, subjetc mangling, etc.)
    """
    __tablename__ = "source_mailinglist"
    id = Column(Integer, ForeignKey(
        'source_imapmailbox.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    # The address through which messages are sent to the list
    post_email_address = Column(UnicodeText, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'source_mailinglist',
        'with_polymorphic': '*'
    }

    def get_send_address(self):
        """
        Get the email address to send a message to the discussion
        """
        return self.post_email()


class AbstractFilesystemMailbox(AbstractMailbox):
    """
    A Mailbox refers to an Email inbox that is stored the server's filesystem.
    """
    __tablename__ = "source_filesystemmailbox"
    id = Column(Integer, ForeignKey(
        'mailbox.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    filesystem_path = Column(CoerceUnicode(), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'source_filesystemmailbox',
    }

class MaildirMailbox(AbstractFilesystemMailbox):
    """
    A Mailbox refers to an Email inbox that is stored as maildir on the server.
    """
    __tablename__ = "source_maildirmailbox"
    id = Column(Integer, ForeignKey(
        'source_filesystemmailbox.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'source_maildirmailbox',
    }
    @staticmethod
    def do_import_content(abstract_mbox, only_new=True):
        abstract_mbox = abstract_mbox.db.merge(abstract_mbox)
        session = abstract_mbox.db
        session.add(abstract_mbox)
        discussion_id = abstract_mbox.discussion_id

        if not os.path.isdir(abstract_mbox.filesystem_path):
            raise "There is no directory at %s" % abstract_mbox.filesystem_path
        else:
            cur_folder_path = os.path.join(abstract_mbox.filesystem_path, 'cur')
            cur_folder_present = os.path.isdir(cur_folder_path)
            new_folder_path = os.path.join(abstract_mbox.filesystem_path, 'new')
            new_folder_present = os.path.isdir(new_folder_path)
            tmp_folder_path = os.path.join(abstract_mbox.filesystem_path, 'tmp')
            tmp_folder_present = os.path.isdir(tmp_folder_path)

            if not (cur_folder_present | new_folder_present | tmp_folder_present):
                raise "Directory at %s is NOT a maildir" % abstract_mbox.filesystem_path
            else:
                #Fix the maildir in case some folders are missing
                #For instance, git cannot store empty folder
                if not cur_folder_present:
                    os.mkdir(cur_folder_path)
                if not new_folder_present:
                    os.mkdir(new_folder_path)
                if not tmp_folder_present:
                    os.mkdir(tmp_folder_path)

        mbox = mailbox.Maildir(abstract_mbox.filesystem_path, factory=None, create=False)
        mails = list(mbox.values())
        #import pdb; pdb.set_trace()
        def import_email(abstract_mbox, message_data):
            session = abstract_mbox.db
            message_string = message_data.as_string()

            (email_object, dummy, error) = abstract_mbox.parse_email(message_string)
            if error:
                raise Exception(error)
            with transaction.manager:
                session.add(email_object)
            abstract_mbox = AbstractMailbox.get(abstract_mbox.id)

        if len(mails):
            [import_email(abstract_mbox, message_data) for message_data in mails]

            #We imported mails, we need to re-thread
            with transaction.manager:
                emails = session.query(Email).filter(
                        Email.discussion_id == discussion_id,
                        ).options(joinedload_all(Email.parent))
                AbstractMailbox.thread_mails(emails)

class Email(ImportedPost):
    """
    An Email refers to an email message that was imported from an AbstractMailbox.
    """
    __tablename__ = "email"

    id = Column(Integer, ForeignKey(
        'imported_post.id',
        ondelete='CASCADE',
        onupdate='CASCADE'
    ), primary_key=True)

    recipients = Column(UnicodeText, nullable=False)
    sender = Column(CoerceUnicode(), nullable=False)

    in_reply_to = Column(CoerceUnicode())

    __mapper_args__ = {
        'polymorphic_identity': 'email',
    }

    def REWRITEMEreply(self, sender, response_body):
        """
        Send a response to this email.

        `sender` is a user instance.
        `response` is a string.
        """

        sent_from = ' '.join([
            "%(sender_name)s on IdeaLoom" % {
                "sender_name": sender.display_name()
            },
            "<%(sender_email)s>" % {
                "sender_email": sender.get_preferred_email(),
            }
        ])

        if type(response_body) == 'str':
            response_body = response_body.decode('utf-8')

        recipients = self.recipients

        message = MIMEMultipart('alternative')
        message['Subject'] = Header(self.subject, 'utf-8')
        message['From'] = sent_from

        message['To'] = self.recipients
        message.add_header('In-Reply-To', self.message_id)

        plain_text_body = response_body
        html_body = response_body

        # TODO: The plain text and html parts of the email should be different,
        # but we'll see what we can get from the front-end.

        plain_text_part = MIMEText(
            plain_text_body.encode('utf-8'),
            'plain',
            'utf-8'
        )

        html_part = MIMEText(
            html_body.encode('utf-8'),
            'html',
            'utf-8'
        )

        message.attach(plain_text_part)
        message.attach(html_part)

        smtp_connection = smtplib.SMTP(
            get_current_registry().settings['mail.host']
        )

        smtp_connection.sendmail(
            sent_from,
            recipients,
            message.as_string()
        )

        smtp_connection.quit()

    def language_priors(self, translation_service):
        priors = super(Email, self).language_priors(translation_service)
        email_obj = email.message_from_string(
            bytes_to_native_str(self.imported_blob))
        locales = {part.get('Content-Language') for part in email_obj.walk()
                   if part.get_content_type() in (
                       'text/plain', 'text/html', 'multipart/alternative')}
        locales.discard(None)
        if locales:
            locales = {translation_service.asKnownLocale(loc)
                       for loc in locales}
            priors = {k: v * (1 if k in locales else 0.8)
                      for (k, v) in priors.items()}
            for lang in locales:
                if lang not in priors:
                    priors[lang] = 1
        return priors

    @as_native_str()
    def __repr__(self):
        return "%s from %s to %s>" % (
            super(Email, self).__repr__(),
            self.sender.encode('iso-8859-1', 'ignore'),
            self.recipients.encode('iso-8859-1', 'ignore'))

    def get_title(self):
        return self.source.mangle_mail_subject(self.subject)
