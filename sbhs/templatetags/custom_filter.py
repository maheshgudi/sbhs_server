from django import template
from django.template.defaultfilters import stringfilter

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