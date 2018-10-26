from django.contrib import admin
from sbhs.models import (Board,	Slot, Experiment, Profile, UserBoard)

admin.site.register(Board)
admin.site.register(Profile)
admin.site.register(Slot)
admin.site.register(Experiment)
admin.site.register(UserBoard)