from django.db import models
from apps.users.models import UserProfile

import amo


class NonAMOAddon(models.Model):
    """This is a non-AMO addon.

    A non-AMO addon is an addon that's not hosted on the addons.m.o website,
    but we want to store its addonid and ask addon developers to register it on
    our APIs.

    We are not extending the amo.Addon model because we don't want to deal with
    all its edge cases. This Model is useful for the file registration API.
    """
    guid = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(blank=True, max_length=255)
    description = models.CharField(blank=True, max_length=500)
    authors = models.ManyToManyField(UserProfile, related_name='nonamo_addons')

    class Meta:
        db_table = 'nonamo_addon'
        ordering = ['guid']


class Hash(amo.models.ModelBase):
    """Each addon can be associated with a number of hashes."""

    addon = models.ForeignKey('filereg.NonAMOAddon', related_name='hashes')
    sha256 = models.CharField(max_length=64, unique=True, primary_key=True)
    registered = models.BooleanField(default=True, blank=True)
    version = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'nonamo_addon_hashes'
        ordering = ['sha256']
