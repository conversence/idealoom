
from builtins import object
from os import urandom
from base64 import b64encode
from subprocess import call
from tempfile import TemporaryFile

from zope import interface

from assembl.lib import config
from assembl.lib.discussion_creation import IDiscussionCreationCallback


@interface.implementer(IDiscussionCreationCallback)
class CreateVMMMailboxAtDiscussionCreation(object):
    """A :py:class:`IDiscussionCreationCallback` that creates an IMAP account with VMM

    Ensure that the following is in /etc/sudoers:
    idealoom_user ALL=NOPASSWD: /usr/sbin/vmm ua *
    """

    def discussionCreated(self, discussion):
        from assembl.models import IMAPMailbox
        for source in discussion.sources:
            if isinstance(source, IMAPMailbox):
                mailbox = source
                break
        if mailbox:
            password = mailbox.password
            email = mailbox.username
            with TemporaryFile() as stderr:
                rcode = call(['sudo', '/usr/sbin/vmm', 'ua', email, password],
                             stderr=stderr)
                if rcode != 0:
                    stderr.seek(0)
                    error = stderr.read()
                    if b" already exists" not in error:
                        raise RuntimeError(
                            "vmm useradd failed: %d\n%s" % (rcode, error))
