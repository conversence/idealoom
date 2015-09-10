class ReadTranslator(object):
    """All translation logic from Jive -> Assembl will be posted here.
    This object is seperate from the Read/Write Sync as it will be used
    in multiple places."""
    pass


class WriteTranslator(object):
    """All translation logic from Assembl -> Jive"""
    pass


class ReadSync(object):
    """The object that is responsible for maintaining a read sync with Jive.
    It is responsible for ensuring unique content and users imported."""
    pass


class WriteSync(object):
    """The object that is responsible for maintaining a write sync with Jive.
    It is responsible for pushing content to Jive."""
    pass


class Synchronizer(ReadSync, WriteSync):
    """This object is responsible for the read and write sync. It ensures
    that both objects behave as expected. Furthermore it ensures that
    written content are not imported (sink behaviour). """
    pass
