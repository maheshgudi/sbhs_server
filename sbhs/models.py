import random, datetime, os
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import ContentType
from django.contrib.auth.models import User, Group, Permission

from sbhs_server import settings
# from django.conf import settings

MOD_GROUP_NAME = 'moderator'


def create_group(group_name, app_label):
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        group = Group(name=group_name)
        group.save()
        # Get the models for the given app
        content_types = ContentType.objects.filter(app_label=app_label)
        permission_list = Permission.objects.filter(
            content_type__in=content_types
        )
        group.permissions.add(*permission_list)
        group.save()
    return group

class Board(models.Model):
    """ SBHS Board attributes"""

    mid = models.IntegerField(unique=True)
    online = models.BooleanField(default=False)

    class Meta:
        ordering = ['mid',]

    def __str__(self):
        return '{}: {}'.format(self.mid, self.online)

class Profile(models.Model):
    """
    Profile model to store user details.
    """
    user = models.OneToOneField(User)
    roll_number = models.CharField(max_length=20)
    institute = models.CharField(max_length=128)
    department = models.CharField(max_length=64)
    position = models.CharField(max_length=64)
    is_moderator = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    activation_key = models.CharField(max_length=255,blank=True,null=True)
    key_expiry_time = models.DateTimeField(blank=True,null=True)

    def _toggle_moderator_group(self, group_name):
        group = Group.objects.get(name=group_name)
        if self.is_moderator:
            self.user.groups.add(group)
        else:
            self.user.groups.remove(group)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            old_profile = Profile.objects.get(pk=self.pk)
            if old_profile.is_moderator != self.is_moderator:
                self._toggle_moderator_group(group_name=MOD_GROUP_NAME)
        super(Profile, self).save(*args, **kwargs)

    def __str__(self):
        return '%s' % (self.user)

class Slot(models.Model):
    user = models.ForeignKey(User)
    start_time = models.DateTimeField("Start time of a slot",
                                      default=timezone.now())
    end_time = models.DateTimeField("End time of a slot",
                default=timezone.now()+timedelta(
                    minutes=settings.SLOT_DURATION))

    def __str__(self):
        return '{} {}'.format(self.start_time, self.end_time)

    def slots_now():
        now = datetime.datetime.now()
        slots = Slot.objects.filter(start_time=now)
        return slots


class Experiment(models.Model):
    slot = models.ForeignKey("Slot")
    log = models.CharField(max_length=255)
    checksum = models.CharField(max_length=255, null=True, blank=True)
