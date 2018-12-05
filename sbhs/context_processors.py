from django.conf import settings

def production_details(request):
	"""
	Context processor to access settings.py CONSTANTS in django
	template.
	"""
	return {
		'sitename':'vlabs.iitb.ac.in/sbhs',
		'domain':settings.PRODUCTION_URL,
		'vlabs_team':settings.SENDER_NAME,
	}