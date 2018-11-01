from django.conf.urls import url
from django.contrib.auth.views import (
    password_reset, password_change, password_change_done, password_reset_done,
    password_reset_confirm, password_reset_complete,
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

    ################## Experiment urls #####################
    url(r'^experiment/check_connection/$',views.check_connection,
            name='experiment_check_connection'),
    url(r'^experiment/initiate/$',views.initiation, 
            name='experiment_initiate'),
    url(r'^experiment/client_version/?$', views.client_version,
            name='experiment_client_version'),
    url(r'^experiment/map_machines/$',views.map_sbhs_to_rpi, 
            name='experiment_initiate'),
    url(r'^experiment/experiment/?$', views.experiment,
           name='experiment_experiment'),
    url(r'^experiment/logs/$',views.logs,name='experiment_logs'),
    url(r'^experiment/logs/([0-9]+)/$',views.download_user_log, 
            name='experiment_logs'),

    ################## Moderator urls #####################
    url(r'^moderator/$',views.moderator_dashboard,
            name='moderator_dashboard'),
    url(r'^moderator/all-bookings/$',views.all_bookings,
            name='all_bookings'),
    url(r'^moderator/profile/(?P<mid>\d+)/$',views.profile, 
            name='profile'),
    url(r'^moderator/log/(?P<mid>\d+)/$',views.download_log, 
            name='download_log'),
    url(r'^moderator/logs_folder_index/?$',views.logs_folder_index, 
            name='logs_folder_index'),    
    url(r'^moderator/all-images/$',views.all_images,name='all_images'),
    url(r'^moderator/update_board_values/(?P<mid>\d+)/$',
            views.update_board_values,
            name='update_board_values'
            ),
    url(r'^moderator/test-boards/$',views.test_boards,name='test_boards'),
    url(r'^moderator/update-mid/$',views.update_mid,name='update_mid'),
    url(r'^moderator/fetch-logs/$',views.fetch_logs,name='fetch_logs'),
    url(r'^moderator/fetch-logs/(?P<experiment_id>\d+)/$',views.download_file, 
            name='download_file'),

    url(r'^moderator/updatemid/$', views.update_mid, name='update_mid'),
    url(r'^moderator/webcam/(?P<mid>\d+)/$',views.show_video_to_moderator,
            name='show_video_to_moderator'),
    ####################### Webcam Url #########################
    url(r'^show_video/$',views.show_video,name='show_video'),
]
