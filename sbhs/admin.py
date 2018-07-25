from django.contrib import admin
from sbhs.models import (Board, Profile, Slot, Booking, Experiment)

admin.site.register(Board)
admin.site.register(Profile)
admin.site.register(Slot)
admin.site.register(Booking)
admin.site.register(Experiment)