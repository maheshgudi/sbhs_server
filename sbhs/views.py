import os
import sys
import time
import json
import random
import zipfile
import inspect
import pytz
# import MySQLdb
import datetime
import requests
import subprocess
# import serial
from textwrap import dedent
from time import gmtime, strftime
from datetime import datetime, timedelta, date

from django.urls import reverse
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.db.models import Count
# import automatic_slot_booking
from django.contrib import messages
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.http import HttpResponse, HttpResponseRedirect,\
    Http404, HttpResponseServerError, JsonResponse
from urllib.parse import urljoin
from .models import Board, Experiment, Profile, Slot#, Webcam
from .forms import UserLoginForm, UserRegistrationForm, SlotCreationForm
from .send_emails import send_user_mail
from sbhs_server import credentials as credentials
from sbhs.decorators import email_verified

################# pages views #######################


def index(request, next_url=None):
    if request.user.is_authenticated():
        return render(request,'account/home.html')
    return render(request,"pages/pages_index.html")

def about(req):
    return render(req, "pages/about.html")


def info(request):
    return render(request,"pages/info.html")

def downloads(req):
    return redirect("http://sbhs.os-hardware.in/downloads")


def theory(req):
    return render(req, "pages/theory.html")

def procedure(req):
    return render(req, "pages/procedure.html")

def experiments(req):
    return render(req, "pages/experiments.html")

def feedback(req):
    return render(req, "pages/feedback.html")

#########Account Views ###########
@email_verified
def account_index(request):
    if request.user.is_authenticated():
        return render(request,'account/home.html')

    return render(request,'account/account_index.html',{
        'login_form':UserLoginForm(request.POST or None),
        'registration_form':UserRegistrationForm(request.POST or None)    
    })

def user_login(request):
    user = request.user
    context = {}
    if user.is_authenticated():
        return account_index(request)

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = authenticate(username=cd['username'],
                                password=cd['password'])
            if user is not None:
                if user.is_active:
                    login(request,user)
                    return redirect('account_enter')
                else:
                    messages.success(request,"Account Disabled")
                    return redirect('account_enter')
            else:
                messages.success(request, "Username and/or Password is \
                                            invalid")
                return redirect('account_enter')
        else:
            context={
                "login_form": form
            }
    else:
        form = UserLoginForm()
        context = {
            "login_form":form
        }
    return redirect('account_enter')

def user_logout(request):
    logout(request)
    return redirect('account_enter')

def user_register(request):
    user = request.user
    if user.is_authenticated():
        return render(request,'account/home.html')
    context={}
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            u_name, pwd, user_email, key= form.save()
            new_user = authenticate(username=u_name,password=pwd)
            login(request, new_user)
            if user_email and key:

                success, msg = send_user_mail(user_email, key)
                context = {
                    'activation_msg':msg
                } 
                return render(request,'account/activation_status.html',
                              context
                )
            return redirect('account_enter')
        else:
            return redirect('account_enter')
    else:
        return redirect('account_enter')

@login_required
def activate_user(request, key):
    profile = get_object_or_404(Profile, activation_key=key)
    context = {}
    context['success'] = False
    if profile.is_email_verified:
        context['activation_msg'] = "Your account is already verified"
        return render(request,'account/activation_status.html',context)
    if timezone.now() > profile.key_expiry_time:
        content['msg'] = dedent(
            """
            Your activation time expired. Please try again
            """
        )
    else:
        context['success'] = True
        profile.is_email_verified=True
        profile.save()
        context['msg'] = "Your account is activated"
    return render(request,'account/activation_status.html',context)

def new_activation(request, email=None):
    context = {}
    if request.method == 'POST':
        email = request.POST.get('email')
    try:
        user = User.objects.get(email=email)
    except MultipleObjectsReturned:
        context['email_err_msg'] = 'Multiple entries found for this email \
                                        Please change your email'
        return render(request,'account/activation_status.html',context)
    except ObjectDoesNotExist:
        context['success'] = False
        context['msg'] = "Your account is not verified. Please verify your \
                            account"
        return render(request, 'account/activation_status.html',context)

    if not user.profile.is_email_verified:
        user.profile.activation_key = generate_activation_key(user.username)
        user.profile.key_expiry_time = timezone.now() \
                                        + timezone.timedelta(minutes=20)
        user.profile.save()
        new_user_data = User.objects.get(email=email)
        success, msg = send_user_mail(new_user_data.email, \
                        new_user_data.profile.activation_key)

        if success:
            context['activation_msg'] = msg
        else:
            context['msg'] = msg
    else:
        context['activation_msg'] = "Your account is already verified"
    return render(request,'account/activation_status.html',{})

@login_required
def update_email(request):
    context = {}
    if request.method == 'POST':
        email = request.POST.get('email')
        username = request.POST.get('username')
        user = get_object_or_404(User, username=username)
        user.email = email
        user.save()
        return new_activation(request, email)
    else:
        context['email_err_msg'] = "Please Update your email"
    return render(request,'account/activation_status.html',context)

@login_required
@email_verified
def slot_new(request):
    user = request.user
    slot_history = Slot.objects.filter(user=user).order_by("start_time")
    context = {}
    now = timezone.now()
    if not request.user.is_authenticated():
        return redirect('account_enter')
    
    if request.method == 'POST':
        if request.POST.get('delete') == "delete":
            slots = request.POST.getlist("slots")
            Slot.objects.filter(id__in=slots).delete()
        if request.POST.get("book_date") == "book_date":
            form = SlotCreationForm(request.POST)
            if form.is_valid():
                new_slot = form.save(commit=False)
                if new_slot.start_time >= now:
                    new_slot.end_time = new_slot.start_time + timedelta(
                                         minutes=settings.SLOT_DURATION
                                         )
                    new_slot.user = user            
                    new_slot.save()
                    messages.success(request,'Slot created successfully.')
                else:
                    messages.error(request,
                                     'Start time selected'
                                     + ' is before today.'
                                     + 'Please choose again.'
                                    )
        if request.POST.get("book_now") == "book_now":
            slot_now = Slot.objects.create(user=user, start_time=now,
                                           end_time=now+timedelta(minutes=55)
                                           )
            messages.success(request,'Slot created successfully.')
        return redirect("slot_new")

    else:
        form = SlotCreationForm()
        context['history']=slot_history
        context['form']=form
        context['now'] = now
    return render(request,'slot/new.html',context)
    


###################Experiment Views ######################

def check_connection(request):
    message = {"message":"TESTOK"}
    return JsonResponse(message, safe=True, status=200)

@login_required
def initial_login(request):
    """ Logs in an user for conducting the experiment on the specified 
        board.
        Input: req:request object.
        Output: HttpResponse object.
    """
    
    username = request.POST.get("username")
    rpi_ip = ''
    try:
        assigned_mid = 2
    except Exception as e:
        return JsonResponse({
            "STATUS":400,
            "MESSAGE":{
                "IS_IP":"1",
                "DATA":"Invalid username"
            }
        })
    rpi_ip = '10.102.54.71'
    if rpi_ip is None:
        return JsonResponse({
                "STATUS":400,
                "MESSAGE":{
                    "IS_IP":"1",
                    "DATA":"Board is currently offline"
                }
        })
    return JsonResponse({
        "STATUS":200,
        "MESSAGE":{
            "IS_IP":"1",
            "DATA":rpi_ip
        }       
    })


@csrf_exempt
def initiation(request):
    username = request.POST.get("username")
    password = request.POST.get("password")
    user = authenticate(username=username, password=password)
    if user:
        if user.is_active:
            now = timezone.now()
            slots = Slot.objects.filter(user=user, 
                        start_time__gte=now, 
                        end_time__lt = now
                        )

            slot = slots.last()
            if slot:
                filename = ''
                message = {
                    "STATUS":1,
                    "MESSAGE": filename
                }       
            else:
                message = {
                    "STATUS":0,
                    "MESSAGE":"Slot has ended. Please book the next slot \
                                to continue the experiment"
                }
        else:
            message = {
                "STATUS":0,
                "MESSAGE":"Your account is not activated. Please check your \
                            mail for activation link"
            }
    else:
        message = {
            "STATUS":0,
            "MESSAGE":"Invalid username and password"
        }

    return JsonResponse(message, safe=True, status=200)

def map_sbhs_to_rpi(client_ip):
    """
    """
    r_pis = settings.RASP_PI_IPS
    map_machines = []
    if r_pis:
        for r_pi in r_pis:
            rpi_map = {}
            rpi_map["rpi_ip"] = r_pi
            rpi_connect = connect_sbhs(r_pi, "get_machine_ids")
            mac_ids = json.loads(rpi_connect)
            board = Board()
            board.save_board_details(r_pi, mac_ids)
            rpi_map["mac_ids"] = [i['sbhs_mac_id'] for i in mac_ids]
            map_machines.append(rpi_map)
    else:
        rpi_map = {}
        client_name = client_ip + ":1234"
        rpi_map["rpi_ip"] = client_name
        rpi_connect = connect_sbhs(client_name, "get_machine_ids")
        mac_ids = json.loads(rpi_connect)
        board = Board()
        board.save_board_details(client_name, mac_ids)

def connect_sbhs(rpi_ip, experiment_url):
    connect_rpi = requests.get("http://{0}/experiment/{1}".format(
                               rpi_ip, experiment_url
                               )
                                )
    return connect_rpi.text

################## Moderator Views ##########################

def is_moderator(user):
    """Check if the user is having moderator rights"""
    if user.profile.is_moderator:
        return True

@login_required
def moderator_dashboard(request):
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page!")
    else:
        all_boards = map_sbhs_to_rpi(request.META["SERVER_NAME"])
        context["all_active_boards"] = all_boards
        return render(request, 'dashboard/dashboard_index.html', context)


# @login_required
# def index(req):
#     user = request.user
#     if not is_moderator(user):
#         raise Http404("You are not allowed to see this page!")
#     boards = Board.objects.order_by('-online').all()
#     allotment_mode = "Random" if Board.can_do_random_allotment() else "Workshop"
#     return render(req, 'admin/index.html', {"boards": boards, "allotment_mode": allotment_mode})

# @login_required
# def toggle_allotment_mode(req):
#     checkadmin(req)
#     Board.toggle_random_allotment()
#     return redirect(index)

# @login_required(redirect_field_name=None)
# def booking_index(req):
#     bookings = Booking.objects.order_by('-booking_date','-slot_id').filter(trashed_at__isnull=True).select_related()[:50]
#     return render(req, 'admin/booking_index.html', {"bookings": bookings})

# @login_required(redirect_field_name=None)
# def webcam_index(req):
#     checkadmin(req)
#     boards = Board.objects.filter(online=True)
#     for board in boards:
#         Webcam.load_image(board.mid)
#     return render(req, 'admin/webcam_index.html', {"boards": boards})

# @login_required(redirect_field_name=None)
# def logs_index(req):
#     checkadmin(req)
#     date = (datetime.datetime.now()).strftime("%Y-%m-%d")
#     return render(req, 'admin/user_logs.html', {"nowdate" : date})

# @login_required(redirect_field_name=None)
# def profile(req, mid):
#     checkadmin(req)
#     try:
#         filename = settings.SBHS_GLOBAL_LOG_DIR + "/" + mid + ".log"
#         f = open(filename, "r")
#         f.close()
#     except:
#         raise Http404

#     delta_T = 1000
#     data = subprocess.check_output("tail -n %d %s" % (delta_T, filename), shell=True)
#     data = data.split("\n")
#     plot = []
#     heatcsv = ""
#     fancsv = ""
#     tempcsv = ""

#     for t in xrange(len(data)):
#         line = data[t]
#         entry = line.strip().split(" ")
#         try:
#             plot.append([int(i) for i in entry[0:-1] + [float(entry[-1])]])
#             heatcsv += "%d,%s\\n" % (t+1, entry[1])
#             fancsv += "%d,%s\\n" % (t+1, entry[2])
#             tempcsv += "%d,%s\\n" % (t+1, entry[3])
#         except:
#             continue

#     plot = zip(*plot) # transpose

#     return render(req, "admin/profile.html", {
#         "mid": mid,
#         "delta_T": delta_T,
#         "heat": heatcsv,
#         "fan": fancsv,
#         "temp": tempcsv
#     })

# @login_required(redirect_field_name=None)
# def testing(req):
#     checkadmin(req)
#     now = datetime.datetime.now()
#     current_slot_id = Slot.objects.filter(start_hour=now.hour,
#                                             start_minute__lt=now.minute,
#                                             end_minute__gt=now.minute)

#     current_slot_id = -1 if not current_slot_id else current_slot_id[0].id

#     current_bookings = Booking.objects.filter(slot_id=current_slot_id,
#                                                 booking_date=datetime.date.today()).select_related()
#     current_mids = list([-1]) if not current_bookings else [current_booking.account.board.mid for current_booking in current_bookings]

#     boards = Board.objects.filter(online=1)
#     allotment_mode = "Random" if Board.can_do_random_allotment() else "Workshop"
#     return render(req, 'admin/testexp.html', {"boards": boards, "allotment_mode": allotment_mode, "mids": current_mids})

# @csrf_exempt
# def monitor_experiment(req):
#     checkadmin(req)
#     try:
#         mid = int(req.POST.get("mid"))
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Invalid parameters"}), content_type="application/json")
#     try:
#         ip = settings.pi_ip_map.get(str(mid))
#         if ip is None:
#             return HttpResponse(json.dumps({"status_code":400, "message":"Board is offline"}), content_type="application/json")
#         url = "http://" + str(ip) + "/pi/admin/monitor"
#         payload = {"mid":mid}
#         r = requests.post(url , data = payload)
        
#         return HttpResponse(r.text, content_type="application/json")
#     except Exception as e:
#         retVal={"status_code":500,"message":"Could not fetch device logs.."}
#         return HttpResponse(json.dumps(retVal),content_type='application/json')

# @login_required(redirect_field_name=None)
# def get_allocated_mids(req):
#     checkadmin(req)
#     with connection.cursor() as cursor:
#         cursor.execute("SELECT tables_board.mid, COUNT(tables_account.id), tables_board.id FROM tables_account RIGHT OUTER JOIN tables_board ON tables_account.board_id = tables_board.id WHERE tables_board.online = 1 GROUP BY tables_board.mid ORDER BY COUNT(tables_account.id)")
#         mid_count = cursor.fetchall()

#     return render(req, 'admin/changeMID.html', {"mid_count" : mid_count})

# @csrf_exempt
# def get_users(req):
#     checkadmin(req)
#     try:
#         users = list(Account.objects.select_related().values_list("username", "board__mid"))
#         return HttpResponse(json.dumps({"status_code":200, "message":users}), content_type="application/json")
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":500, "message":str(e)}), content_type="application/json")


# @csrf_exempt
# def toggle_device_status(req):
#     checkadmin(req)

#     try : 
#         mid = req.POST.get('mid')
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Invalid parameters"}), content_type="application/json")

#     try:
#         now = datetime.datetime.now()
#         current_slot_id = Slot.objects.filter(start_hour=now.hour,
#                                                 start_minute__lt=now.minute,
#                                                 end_minute__gt=now.minute)

#         current_slot_id = -1 if not current_slot_id else current_slot_id[0].id

#         current_bookings = Booking.objects.filter(slot_id=current_slot_id,
#                                                     booking_date=datetime.date.today()).select_related()
#         current_mids = list([-1]) if not current_bookings else [current_booking.account.board.mid for current_booking in current_bookings]
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Unsuccessful"}), content_type="application/json")

#     if int(mid) in current_mids:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Board is in use."}), content_type="application/json")

#     try:
#         brd = Board.objects.get(mid = mid)
#         brd.temp_offline = not brd.temp_offline
#         brd.save()

#         return HttpResponse(json.dumps({"status_code":200, "message":"Toggle successful"}), content_type="application/json")
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":500, "message":"Unsuccessful"}), content_type="application/json")


# def user_exists(username):
#     try:
#         user = Account.objects.get(username=username)
#     except ObjectDoesNotExist:
#         return None
#     return user

# @csrf_exempt
# def update_allocated_mid(req):
#     checkadmin(req)
#     try:
#         username = req.POST.get("username")
#         board_id = req.POST.get("board_id")
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Invalid parameters"}), content_type="application/json")

#     user = user_exists(username)
#     if user is not None:
#         user.board_id = board_id
#         user.save()
#     else:
#         return HttpResponse(json.dumps({"status_code": 400, "message": "Username does not exist"}), content_type="application/json")

#     return HttpResponse(json.dumps({"status_code": 200, "message": "MID changed successfully"}), content_type="application/json")

# @login_required(redirect_field_name=None)
# def download_log(req, mid):
#     checkadmin(req)
#     try:
#         global_logfile = settings.SBHS_GLOBAL_LOG_DIR + "/" + mid + ".log"
#         f = open(global_logfile, "r")
#         data = f.read()
#         f.close()
#         return HttpResponse(data, content_type='text/text')
#     except:
#         return HttpResponse("Requested log file doesn't exist.Please Try in the next hour after your slot ends.")

# @login_required(redirect_field_name=None)
# @csrf_exempt
# def range_logs(req):
#     checkadmin(req)
#     try:
#         start_date = req.POST.get("start_date")
#         end_date = req.POST.get("end_date")
#         start_time = req.POST.get("start_time")
#         end_time = req.POST.get("end_time")
#     except:
#         return HttpResponse(json.dumps({"status_code":400, "message":"Invalid parameters"}), content_type="application/json")

#     try:
#         start = start_date + " " + start_time
#         end = end_date + " " + end_time
#         log_files = Experiment.objects.filter(created_at__range=[start, end]).values("id", "log")

#         return HttpResponse(json.dumps({"status_code":200, "message":list(log_files)}), content_type="application/json")
#     except Exception as e:
#         return HttpResponse(json.dumps({"status_code": 500, "message": "Some error occured" + str(e)}), content_type="application/json")

# @login_required(redirect_field_name=None)
# @csrf_exempt
# def download_experiment_log(req, experiment_id):
#     """ Downloads the experimental log file.
#         Input: req: request object, experiment_id: experimental id
#         Output: HttpResponse object
#     """
#     checkadmin(req)
#     try:
#         experiment_data = Experiment.objects.select_related("booking", "booking__account").get(id=experiment_id)
#         f = open(os.path.join(settings.EXPERIMENT_LOGS_DIR, experiment_data.log), "r")
#         data = f.read()
#         f.close()
#         return HttpResponse(data, content_type='text/text')
#     except:
#         return HttpResponse("Requested log file doesn't exist.")

# @csrf_exempt
# def reset_device(req):
#     """Resets the device to fan = 100 and heat = 0
#         Takes mid as paramter 
#         Returns status_code = 200, data={temp:temp of the device} if succesful
#                 else 
#                 status_code = 500 , data={error:errorMessage}
#     """ 
#     checkadmin(req)
#     mid=int(req.POST.get('mid'))

#     try:
#         ip = settings.pi_ip_map.get(str(mid))
#         if ip is None:
#             return HttpResponse(json.dumps({"status_code":400, "message":"Board is offline"}), content_type="application/json")
#         url = "http://" + str(ip) + "/pi/admin/resetdevice"
#         payload = {"mid":mid}
#         r = requests.post(url , data = payload)
        
#         return HttpResponse(r.text, content_type="application/json")
#     except Exception as e:
#         retVal={"status_code":500,"message":"Could not reset the device.."}
#         return HttpResponse(json.dumps(retVal),content_type='application/json')


# @csrf_exempt
# def set_device_params(req):
#     """Sets the device parameters as per the arguments sent
#         Takes mid,fan,heat as paramter 
#         Returns status_code = 200, data={temp:temp of the device} if succesful
#                 else 
#                 status_code = 500 , data={error:errorMessage}
#     """ 
#     checkadmin(req)
#     mid=int(req.POST.get('mid'))
#     fan=int(req.POST.get('fan'))
#     heat=int(req.POST.get('heat'))
#     try:
#         ip = "192.168.1.141"
#         # ip = settings.pi_ip_map.get(str(mid))
#         # if ip is None:
#         #     return HttpResponse(json.dumps({"status_code":400, "message":"Board is offline"}), content_type="application/json")
#         # url = "http://" + str(ip) + "/pi/admin/setdevice"
#         # payload = {"mid":mid, "fan":fan, "heat":heat}
#         # r = requests.post(url , data = payload)
#         s = Sbhs()
#         fan = s.setFan(ip,fan)
#         heat = s.setHeat(ip,heat)
#         payload = {"ip":ip,"fan":fan,"heat":heat}
#         # return HttpResponse(r.text, content_type="application/json")
#         return HttpResponse(payload,content_type="application/json")
#     except Exception as e:
#         retVal={"status_code":500,"message":"Could not set the device params.."}
#         return HttpResponse(json.dumps(retVal),content_type='application/json')

# @csrf_exempt
# def get_device_temp(req):
#     """Sets the device parameters as per the arguments sent
#         Takes mid,fan,heat as paramter 
#         Returns status_code = 200, data={temp:temp of the device} if succesful
#                 else 
#                 status_code = 500 , data={error:errorMessage}
#     """ 
#     checkadmin(req)
#     # mid=int(req.POST.get('mid'))
#     try:
#     #     ip = settings.pi_ip_map.get(str(mid))
#     #     if ip is None:
#     #         return HttpResponse(json.dumps({"status_code":400, "message":"Board is offline"}), content_type="application/json")
#     #     url = "http://" + str(ip) + "/pi/admin/gettemp"
#     #     payload = {"mid":mid}
#     #     r = requests.post(url , data = payload)
#         ip = "192.168.1.141"
#         s = Sbhs()
#         contents = s.getTemp(ip)
#         print("contents: {}".format(contents))
#         # return HttpResponse(r.text, content_type="application/json")
#         return HttpResponse(json.dumps({"status_code": 200,"contents":contents}),content_type="application/json")
#     except Exception as e:
#         retVal={"status_code":500,"message":"Could not get the device temperature.."+str(e)}
#         return HttpResponse(json.dumps(retVal),content_type='application/json')
