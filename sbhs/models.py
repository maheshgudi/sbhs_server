import random, datetime, os

from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.models import ContentType

from sbhs_server import settings

MOD_GROUP_NAME = 'moderator'


def create_group(group_name, app_label):
    try:
        group=Group.objects.get(name=group_name)
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

    # def allot_board():
    #     if Board.can_do_random_allotment():
    #         online_boards_count = len(settings.online_mids)
    #         board_num = random.randrange(online_boards_count)
    #         return settings.online_mids[board_num]
    #     else:
	   #  online_boards = [int(x) for x in settings.online_mids]
    #         online_boards = sorted(online_boards)

    #         # When the account table is empty, allocate first board 
    #         try:
    #             last_allocated_MID = Account.objects.select_related().order_by("-id")[0].board.mid;
    #             for o in online_boards:
    #                 if int(o) > last_allocated_MID:
    #                     return Board.objects.get(mid=o).id
    #         except Exception as e:
    #             pass
            
    #         # check if there is at least one online board
    #         try:
    #             return Board.objects.get(mid=online_boards[0]).id    
    #         except Exception as e:
    #             return -1    

    # def image_link(self):
    #     """ Function to show the image obtained from webcam
    #     """
    #     return settings.WEBCAM_STATIC_DIR + "image" + '0'+str(self.mid) + ".jpeg"

class Profile(models.Model):
    """
    Profile model to store user details.
    """
    user=models.OneToOneField(User)
    roll_number = models.CharField(max_length=20)
    institute = models.CharField(max_length=128)
    department=models.CharField(max_length=64)
    position=models.CharField(max_length=64)
    is_moderator=models.BooleanField(default=False)
    is_email_verified=models.BooleanField(default=False)
    activation_key=models.CharField(max_length=255,blank=True,null=True)
    key_expiry_time=models.DateTimeField(blank=True,null=True)

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
    start_time = models.DateTimeField("Start time of a slot")
    duration = models.IntegerField(default=settings.SLOT_DURATION)

    def __str__(self):
        return '{} {}'.format(self.start_time, self.duration)


class Experiment(models.Model):
    slot = models.ForeignKey("Slot")
    log = models.CharField(max_length=255)
    checksum = models.CharField(max_length=255, null=True, blank=True)

# class Webcam():
#     """
#     Utility function to capture webcam feeds using streamer
#     """
#     def __init__(self):
#         pass

#     @classmethod
#     def load_image(className,mid):
        
#         if int(mid) :
#             command = "timeout 2s streamer -q -f jpeg -c /dev/video" + '0'+str(mid)
#             print 'command1', command
#             command += " -o " + settings.WEBCAM_DIR + "image" + '0'+str(mid) + ".jpeg"
#             print 'command2', command
#             os.system(command)
#             