from django import template
from django.template.defaultfilters import stringfilter
from sbhs.models import Slot

register = template.Library()

@register.simple_tag
def compare_slot_time(start_time, end_time, now):
    slot = "pending"
    if start_time <= now <= end_time:
    	slot ="ongoing"
    elif start_time >= now:
    	slot ="pending"
    else:
    	slot = "finished"
    return slot


@register.simple_tag
def check_board_occupancy(mid):
    slot = Slot.objects.get_active_slot_for_board(mid)
    if slot:
        return True
    else:
        return False
