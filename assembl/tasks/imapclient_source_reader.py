import logging
from datetime import datetime, timedelta
from imaplib import IMAP4

from imapclient import IMAPClient
from sqlalchemy.orm import undefer

import ssl
import certifi

from assembl.models import ContentSource, Post, AbstractMailbox, ImportedPost, Email
from .source_reader import (
    ReaderStatus, SourceReader, ReaderError, ClientError, IrrecoverableError)

log = logging.getLogger(__name__)


class IMAPReader(SourceReader):
    """A :py:class:`assembl.tasks.source_reader.SourceReader`
    subclass for reading IMAP messages with IMAPClient. Can wait for push."""

    max_idle_period = timedelta(minutes=29)

    def __init__(self, source_id):
        super(IMAPReader, self).__init__(source_id)
        self.selected_folder = False
        self.mailbox = None
        self.idling = False
        log.disabled = False

    def login(self):
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            # context.check_hostname = False
            # context.verify_mode = ssl.CERT_NONE
            mailbox = IMAPClient(
                self.source.host,
                port=self.source.port,
                use_uid=True,
                ssl=self.source.use_ssl,
                ssl_context=context)
            # mailbox.debug = 5
            capabilities = mailbox.capabilities()
            if b'STARTTLS' in capabilities:
                # Always use starttls if server supports it
                mailbox.starttls(context)
            if b'IDLE' in capabilities:
                self.can_push = True
            mailbox.login(self.source.username, self.source.password)
            mailbox.select_folder(self.source.folder)
            self.selected_folder = True
            self.mailbox = mailbox
        except IMAP4.abort as e:
            raise IrrecoverableError(e)
        except IMAP4.error as e:
            raise ClientError(e)

    def wait_for_push(self):
        assert self.can_push
        try:
            start_time = datetime.now()
            found_emails = []
            limit = start_time + self.max_idle_period
            if not self.idling:
                self.mailbox.idle()
                self.idling = True
            self.set_status(ReaderStatus.WAIT_FOR_PUSH)
            while (datetime.now() < limit) and not found_emails and (
                    self.status == ReaderStatus.WAIT_FOR_PUSH):
                elapsed = datetime.now() - start_time
                timeout = max(
                    1, int((self.max_idle_period - elapsed).total_seconds()))
                resps = self.mailbox.idle_check(timeout)
                if not resps:
                    # No "hello, possibly a timeout"
                    break
                for resp in resps:
                    if (resp[0] == b'OK' and resp[1] == b'Still here'):
                        continue
                    if resp[1] == b'EXISTS':
                        found_emails.append(resp[0])
            if self.status == ReaderStatus.WAIT_FOR_PUSH:
                self.end_wait_for_push()
            if found_emails:
                self.process_email_ids(found_emails)
            self.set_status(ReaderStatus.WAIT_FOR_PUSH)
        except (IMAP4.abort, IMAP4.error) as e:
            raise ClientError(e)
        except AssertionError as e:
            # Case where we're closing from another thread
            pass

    def end_wait_for_push(self):
        if self.idling and self.status in (
                ReaderStatus.WAIT_FOR_PUSH, ReaderStatus.CLOSED,
                ReaderStatus.SHUTDOWN):
            try:
                self.mailbox.idle_done()
            except (IMAP4.abort, IMAP4.error) as e:
                log.warning(str(e))
                # Maybe we ended from another thread
                pass
            finally:
                self.idling = False
        super(IMAPReader, self).end_wait_for_push()

    def shutdown(self):
        super(IMAPReader, self).shutdown()
        if self.idling:
            self.end_wait_for_push()

    def do_close(self):
        exc = None
        self.idling = False
        if self.selected_folder:
            try:
                self.mailbox.close_folder()
            except (IMAP4.abort, IMAP4.error) as e:
                exc = ClientError(e)
            finally:
                self.selected_folder = False
        if self.mailbox:
            try:
                self.mailbox.logout()
            except (IMAP4.abort, IMAP4.error) as e:
                exc = ClientError(e)
            finally:
                self.mailbox = None
        if exc is not None:
            raise exc

    def import_email(self, email_id):
        mailbox = self.mailbox
        # log.debug( "running fetch for message: "+email_id)
        try:
            messages = self.mailbox.fetch([email_id], [b"RFC822"])

            # log.debug( repr(messages))
            message_string = messages[email_id][b"RFC822"]
            assert message_string
            message_string = AbstractMailbox.guess_encoding(message_string)
            try:
                if self.source.message_ok_to_import(message_string):
                    (email_object, dummy, error) = self.source.parse_email(message_string)
                    if error:
                        raise ReaderError(error)
                    self.source.db.add(email_object)
                else:
                    log.info("Skipped message with imap id %s (bounce or vacation message)" % (email_id))
                # log.debug( "Setting self.source.last_imported_email_uid to "+email_id)
                self.source.last_imported_email_uid = email_id
                self.source.db.commit()
            finally:
                self.source = ContentSource.get(self.source.id)
        except (IMAP4.abort, IMAP4.error) as e:
            raise ClientError(e)

    def process_email_ids(self, email_ids):
        self.set_status(ReaderStatus.READING)
        self.refresh_source()
        log.info("Processing messages from IMAP: %d "% (len(email_ids)))
        for email_id in email_ids:
            self.import_email(email_id)
            if self.status != ReaderStatus.READING:
                break
        # We imported mails, we need to re-thread
        self.source.db.flush()
        # Rethread emails globally (sigh)
        emails = self.source.db.query(Email).filter_by(
            discussion_id=self.source.discussion_id
        ).options(undefer(ImportedPost.imported_blob)).all()

        AbstractMailbox.thread_mails(emails)
        self.source.db.commit()

    def do_read(self):
        only_new = not self.reimporting
        try:
            self.set_status(ReaderStatus.READING)
            mailbox = self.mailbox
            command = b"ALL"
            search_status = None

            email_ids = None
            if only_new and self.source.last_imported_email_uid:
                command = "%s:*" % self.source.last_imported_email_uid

                email_ids = mailbox.search(command, 'utf-8')
                #log.debug(email_ids)

            if (only_new and search_status == b'OK' and email_ids
                    and email_ids[0] == self.source.last_imported_email_uid):
                # Note:  the email_ids[0]==self.source.last_imported_email_uid test is
                # necessary beacuse according to https://tools.ietf.org/html/rfc3501
                # seq-range like "3291:* includes the UID of the last message in
                # the mailbox, even if that value is less than 3291."

                # discard the first message, it should be the last imported email.
                del email_ids[0]
            else:
                # Either:
                # a) we don't import only new messages or
                # b) the message with self.source.last_imported_email_uid hasn't been found
                #    (may have been deleted)
                # In this case we request all messages and rely on duplicate 
                # detection
                command = b"ALL"
                email_ids = mailbox.search(b"ALL", 'utf-8')

            if len(email_ids):
                self.process_email_ids(email_ids)
            else:
                log.debug("No IMAP messages to process")
            self.successful_read()
            self.set_status(ReaderStatus.PAUSED)
        except (IMAP4.abort, IMAP4.error) as e:
            raise ClientError(e)
