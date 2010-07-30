from django.db import models
from django.db.models.fields import related

from versions.base import revision
from versions.constants import VERSIONS_STATUS_CHOICES, VERSIONS_STATUS_PUBLISHED, VERSIONS_STATUS_DELETED, VERSIONS_STATUS_STAGED_EDITS, VERSIONS_STATUS_STAGED_DELETE
from versions.exceptions import VersionsException
from versions.managers import VersionsManager

class VersionsOptions(object):
    @classmethod
    def contribute_to_class(klass, cls, name):
        include = getattr(klass, 'include', [])
        exclude = getattr(klass, 'exclude', [])

        invalid_excludes = set(['_versions_status']).intersection(exclude)
        if invalid_excludes:
            raise VersionsException('You cannot include `%s` in a VersionOptions exclude.' % ', '.join(invalid_excludes))

        cls._versions_options = VersionsOptions()
        cls._versions_options.include = include
        cls._versions_options.exclude = exclude
        cls._versions_options.core_include = ['_versions_status']
        cls._versions_options.repository = getattr(klass, 'repository', 'default')

class VersionsModel(models.Model):
    _versions_status = models.PositiveIntegerField(choices=VERSIONS_STATUS_CHOICES, default=VERSIONS_STATUS_PUBLISHED)
    def versions_status(self):
        return self._versions_status
    versions_status = property(versions_status)

    objects = VersionsManager()

    class Meta:
        abstract = True

    class Versions(VersionsOptions):
        exclude = []
        include = []

    # Used to store the revision of the model.
    _versions_revision = None
    _versions_staged_changes = None
    _versions_related_updates = None

    def __init__(self, *args, **kwargs):
        self._versions_revision = None
        self._versions_related_updates = {}
        self._versions_staged_changes = {}
        super(VersionsModel, self).__init__(*args, **kwargs)

    def __save_base(self, *args, **kwargs):
        super(VersionsModel, self).save()

        for field, model_instance in self._versions_related_updates.items():
            related_field = self._meta.get_field(field).related.get_accessor_name()
            revision.stage_related_update(self, field, None, model_instance)

    def save(self, *args, **kwargs):
        if (self._get_pk_val() is None or self._versions_status in (VERSIONS_STATUS_PUBLISHED, VERSIONS_STATUS_DELETED)):
            self.__save_base(*args, **kwargs)
        return revision.stage(self)

    def delete(self, *args, **kwargs):
        if self._versions_status in (VERSIONS_STATUS_STAGED_EDITS, VERSIONS_STATUS_STAGED_DELETE,):
            self._versions_status = VERSIONS_STATUS_STAGED_DELETE
        else:
            self._versions_status = VERSIONS_STATUS_DELETED
        return self.save()

    def commit(self):
        if self._versions_status == VERSIONS_STATUS_STAGED_DELETE:
            self._versions_status = VERSIONS_STATUS_DELETED
        elif self._versions_status == VERSIONS_STATUS_STAGED_EDITS:
            self._versions_status = VERSIONS_STATUS_PUBLISHED

        # We don't want to call our main save method, because we want to delay
        # staging the state of this model until we set the state of all unpublihsed manytomany edits.
        self.__save_base()

        if self._versions_revision is None:
            data = revision.data(self)
        else:
            data = revision.version(self, rev=self._versions_revision)

        for name, ids in data['related'].items():
            try:
                field = self._meta.get_field_by_name(name)[0]
            except:
                pass
            else:
                if isinstance(field, related.ManyToManyField):
                    setattr(self, name, self._versions_staged_changes.get(name, ids))

        return revision.stage(self)

    def stage(self):
        self._versions_status = VERSIONS_STATUS_STAGED_EDITS
        return self.save()
