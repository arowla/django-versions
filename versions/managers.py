from django.db import connection
from django.db import models

from versions.repo import versions
from versions.query import VersionsQuerySet, VersionsQuery

class VersionsManager(models.Manager):
    use_for_related_fields = True

    def version(self, revision):
        return self.get_query_set(revision)

    def revisions(self, instance):
        return [ x.hex() for x in versions.revisions(instance) ]

    def diff(self, instance, rev0, rev1=None):
        return versions.diff(instance, rev0, rev1)

    def get_query_set(self, revision=None):
        if self.related_model_instance is not None:
            revision = revision and revision or self.related_model_instance._versions_revision

        qs = VersionsQuerySet(model=self.model, query=VersionsQuery(self.model, connection, revision=revision), revision=revision)

        # If we are looking up the current state of the model instances, filter out deleted models. The Versions system will take care of filtering out the deleted revised objects.
        if revision is None:
            qs = qs.filter(versions_deleted=False)

        return qs

class PublishedManager(VersionsManager):
    def get_query_set(self, revision=None):
        qs = super(PublishedManager, self).get_query_set(revision)

        if self.related_model_instance is not None:
            revision = revision and revision or self.related_model_instance._versions_revision

        # If we are looking up the current state of the model instances, filter out unpublished models.
        if revision is None:
            qs = qs.filter(versions_published=True)

        return qs
