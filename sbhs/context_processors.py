from django.conf import settings

def production_details(request):
	"""
	Context processor to access settings.py CONSTANTS in django
	template.
	"""
	context={}
	context['sitename'] = request.META['HTTP_HOST']
	context['domain'] = settings.PRODUCTION_URL
	context['vlabs_team'] = settings.SENDER_NAME
	return context