"""Infrastructure to route CRUD events through Celery_, and create Notification objects.

.. _Celery: http://www.celeryproject.org/
"""
from . import celery
from ..lib.model_watcher import BaseModelEventWatcher
import transaction
_dispatcher = None


@celery.task()
def processPostCreatedTask(id):
    with transaction.manager:
        get_dispatcher().processPostCreated(id)


@celery.task()
def processPostModifiedTask(id, state_changed):
    with transaction.manager:
        get_dispatcher().processPostModified(id, state_changed)


class ModelEventWatcherCelerySender(BaseModelEventWatcher):
    """A IModelEventWatcher that will receive CRUD events and send postCreated through Celery_"""

    def processPostCreated(self, id):
        processPostCreatedTask.delay(id)

    def processPostModified(self, id, state_changed):
        processPostModifiedTask.delay(id, state_changed)


def get_dispatcher():
    global _dispatcher
    if not _dispatcher:
        from ..models.notification import (
            ModelEventWatcherNotificationSubscriptionDispatcher)
        _dispatcher = ModelEventWatcherNotificationSubscriptionDispatcher()
    return _dispatcher
