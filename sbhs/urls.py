from django.conf.urls import url
from django.contrib.auth.views import (
    password_reset, password_change, password_change_done, password_reset_done,
    password_reset_confirm, password_reset_complete
    )
from . import views

urlpatterns = [
    ################## Account URLS ####################
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

    # change password urls
    url(r'^account/password-change/$', password_change, 
            {'template_name': 'account/registration/password_change_form.html'},
            name='password_change'),
    url(r'^account/password-change/done/$', password_change_done, 
            {'template_name': 'account/registration/password_change_done.html'},
            name='password_change_done'),

    # restore password urls
    url(r'^account/password-reset/$', password_reset, 
           {'template_name': 'account/registration/password_reset_form.html'}, 
           name='password_reset'),
    url(r'^account/password-reset/done/$', password_reset_done, 
            {'template_name': 'account/registration/password_reset_done.html'}, 
            name='password_reset_done'),
    url(r'^account/password-reset/confirm/(?P<uidb64>[-\w]+)/(?P<token>[-\w]+)/$', 
            password_reset_confirm, 
            {'template_name': 'account/registration/password_reset_confirm.html'},
            name='password_reset_confirm'),
    url(r'^account/password-reset/complete/$', password_reset_complete, 
            {'template_name': 'account/registration/password_reset_complete.html'},
            name='password_reset_complete'),

    ################## Slot Urls #######################
    url(r'^slot/new/$',views.slot_new,name='slot_new'),

    ################## Dashboard Urls ######################
    url(r'^dashboard/$',views.dashboard_index, name='dashboard_index'),

    ################## Experiment urls #####################
    url(r'^experiment/check_connection/$',views.check_connection,
            name='experiment_check_connection'),

    url(r'^experiment/initiate/$',views.initiation,name='experiment_initiate')
]
