from django.db import models
from django.contrib.auth.models import User, Group
import random, datetime, os
from sbhs_server import settings


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
    user = models.ForeignKey(User)  
    is_verified = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)


class Slot(models.Model):
    start_time = models.DateTimeField("Start time of a slot")
    duration = models.IntegerField(default=settings.SLOT_DURATION)


class Booking(models.Model):
    user = models.ForeignKey(User)
    slot = models.ForeignKey(Slot)


class Experiment(models.Model):
    booking = models.ForeignKey("Booking")
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