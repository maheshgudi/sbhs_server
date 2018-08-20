from django.conf.urls import url

from . import views

urlpatterns = [
    ####### Account URLS ########
    url(r'^$', views.index, name='pages_index'),
    url(r'^about/?$', views.about, name='pages_about'),
    # url(r'^contact/?$', views.contact, name='pages_contact'),
    url(r'^info/?$', views.info, name='pages_info'),
    url(r'^downloads/?$', views.downloads, name='pages_downloads'),
    url(r'^theory/?$', views.theory, name='pages_theory'),
    url(r'^procedure/?$', views.procedure, name='pages_procedure'),
    url(r'^experiments/?$', views.experiments, name='pages_experiments'),
    url(r'^feedback/?$', views.feedback, name='pages_feedback'),
    
    url(r'^account/enter/$',views.account_index,name='account_enter'),
    url(r'^account/login/$',views.user_login,name='account_login'),
    url(r'^account/logout/$',views.user_logout,name='account_logout'),
    url(r'^account/create/$',views.user_register,name='account_create'),
    url(r'^account/activate/(?P<key>.+)$', views.activate_user, 
            name="activate"),
    url(r'^account/new_activation/$',views.new_activation, 
            name='new_activation'),
    url(r'^account/update_email/$',views.update_email, \
            name='update_email'),

    url(r'^slot/new/$',views.slot_new,name='slot_new'),
]
