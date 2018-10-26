import os
import sys
import time
import json
import random
import zipfile
import inspect
import pytz
import datetime
import requests
import subprocess, zipfile
# import serial
from textwrap import dedent
from time import gmtime, strftime
import time
from datetime import datetime, timedelta, date

from django.urls import reverse
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth.models import User
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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


from .models import Board, Experiment, Profile, Slot, UserBoard#, Webcam
from .forms import (
    UserLoginForm, UserRegistrationForm, SlotCreationForm, FilterLogsForm
    )
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
    user = request.user
    if user.is_authenticated():
        if not UserBoard.objects.filter(user=user).exists():
            random_board = Board.objects.order_by('?').last()
            UserBoard.objects.create(user=user, board=random_board)
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
    slot_history = Slot.objects.filter(user=user).order_by("-start_time")
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
    return HttpResponse("TESTOK")

def client_version(request):
    return HttpResponse(str(settings.CLIENT_VERSION))

   
@csrf_exempt
def initiation(request):
    username = request.POST.get("username")
    password = request.POST.get("password")
    user = authenticate(username=username, password=password)
    if user:
        if user.is_active:
            now = timezone.now()
            slots = Slot.objects.get_current_slots(user).order_by("id")
            slot = slots.last()
            board = UserBoard.objects.get(user=user).board
            check_status_path = "reset/{0}".format(board.usb_id)
            check_status = connect_sbhs(board.raspi_path, check_status_path)
            if check_status["status"] and slot:
                filename = datetime.strftime(now, "%Y%b%d_%H_%M_%S.txt")
                logdir = os.path.join(settings.EXPERIMENT_LOGS_DIR,
                                      user.username
                                      )
                user_file = user.username + "/" + filename
                if not os.path.exists(logdir):
                    os.makedirs(logdir)
                
                if not Experiment.objects.filter(slot=slot,
                                                  log=user_file
                                                  ).exists():
                    Experiment.objects.create(slot=slot,
                                              log=user_file
                                              )
                
                message = {
                    "STATUS":1,
                    "MESSAGE": filename,
                }
            elif check_status["status"] and not slot:
                message = {
                    "STATUS":0,
                    "MESSAGE":"Slot has ended. Please book the next slot."
                }
            elif not check_status["status"] and slot:
                message = {
                    "STATUS":0,
                    "MESSAGE":"Slot is booked but Board is currently offline."
                }
            else:
                message = {
                    "STATUS":0,
                    "MESSAGE":"Board is currently offline. Contact admin."
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
            mac_ids = connect_sbhs(r_pi, "get_machine_ids")
            for devices in mac_ids: 
                board = Board()
                board.save_board_details(r_pi, devices)
            rpi_map["mac_ids"] = [i['sbhs_mac_id'] for i in mac_ids]
            map_machines.append(rpi_map)
    else:
        rpi_map = {}
        rpi_map["rpi_ip"] = client_name
        mac_ids = connect_sbhs(client_name, "get_machine_ids")
        board = Board()
        board.save_board_details(client_name, mac_ids)
        rpi_map["mac_ids"] = [i['sbhs_mac_id'] for i in mac_ids]
        map_machines.append(rpi_map)
    return map_machines

def connect_sbhs(rpi_ip, experiment_url):
    connect_rpi = requests.get("http://{0}/experiment/{1}".format(
                               rpi_ip, experiment_url
                               )
                                )
    data = json.loads(connect_rpi.text)
    return data

@csrf_exempt
def experiment(request):
    try:
        username = request.POST.get("username") 
        server_start_ts = int(time.time() * 1000)
        user = User.objects.get(username=username)
        slot = Slot.objects.get_current_slots(user)\
                            .order_by("start_time").last()
        board = UserBoard.objects.get(user=user).board
        experiment = Experiment.objects.filter(slot=slot)
        if experiment.exists():
            experiment = experiment.first()
            now = timezone.now()
            endtime = slot.end_time
            if endtime > now:
                timeleft = int((endtime-now).seconds)
                heat = max(min(int(request.POST.get("heat")), 100), 0)
                fan = max(min(int(request.POST.get("fan")), 100), 0)
                set_heat_url = "set_heat/{0}/{1}".format(board.usb_id, heat)
                set_fan_url = "set_fan/{0}/{1}".format(board.usb_id, fan)
                get_temp_url = "get_temp/{0}".format(board.usb_id)
                set_heat = connect_sbhs(board.raspi_path, set_heat_url)
                set_fan = connect_sbhs(board.raspi_path, set_fan_url)
                get_temp = connect_sbhs(board.raspi_path,get_temp_url)
                temp = get_temp["temp"]
                log_data(board.mid, heat, fan, temp)

                server_end_ts = int(time.time() * 1000)

                STATUS = 1
                MESSAGE = "%s %d %d %2.2f" % (request.POST.get("iteration"),
                                            heat,
                                            fan,
                                            temp)
                MESSAGE = "%s %s %d %d,%s,%d" % (MESSAGE,
                                            request.POST.get("timestamp"),
                                            server_start_ts,
                                            server_end_ts,
                                            request.POST.get("variables"), 
                                            timeleft)
                experiment_log_path = os.path.join(
                                         settings.EXPERIMENT_LOGS_DIR,
                                         experiment.log
                                         )
                f = open(experiment_log_path, "a")
                f.write(" ".join(MESSAGE.split(",")[:2]) + "\n")
                f.close()
                # Experiment.objects.create(slot=slot, log=experiment_log_path)
            else:
                STATUS = 0
                MESSAGE = "Slot has ended. Please book the next slot to \
                            continue the experiment."
        else:
            STATUS = 0
            MESSAGE = "You haven't booked this slot."

        return HttpResponse(json.dumps({"STATUS": STATUS, "MESSAGE": MESSAGE}))
    except Exception as e:
        raise Exception
        return HttpResponse(json.dumps({"STATUS": 0,
                                        "MESSAGE": "Please Contact Admin"
                                        }
                                        )
                            )

def log_data(mid, heat, fan, temp):
        
    data = "{0} {1} {2} {3}\n".format(int(time.time()),str(heat),
                                  str(fan), str(temp)
                                  )
    global_logfile = settings.SBHS_GLOBAL_LOG_DIR + "/" + str(mid) + ".log"
    try:
        with open(global_logfile, "a") as global_loghandler:
            global_loghandler.write(data)
        return True
    except:
        return False

@login_required
def logs(request):
    user = request.user
    context = {}
    all_bookings = Slot.objects.filter(user__username=user)
    all_booking_ids = [booking.id for booking in all_bookings]
    experiment = Experiment.objects.select_related("slot").filter(slot_id__in=all_booking_ids)
    for exp in experiment:
        exp.logname = exp.log.split("/")[-1]
        context['exp.logname'] = exp.logname 
    context['experiment'] = experiment
    return render(request,'experiment/logs.html',context)

@login_required
def download_user_log(request, experiment_id):
    user = request.user
    experiment_data = Experiment.objects.get(slot__id=experiment_id)
    f = open(os.path.join(settings.EXPERIMENT_LOGS_DIR, experiment_data.log),"r")
    data = f.read()
    print(data)
    f.close()
    return HttpResponse(data, content_type="text/text")
    

# @csrf_exempt
# def reset(req):
#     try:
#         from pi_server.settings import boards
#         user = req.user
#         if user.is_authenticated():
#             key = str(user.board.mid)
#             experiment = Experiment.objects.select_related().filter(id=boards[key]["experiment_id"])

#             if len(experiment) == 1 and user == experiment[0].booking.account:
#                 experiment = experiment[0]
#                 now = datetime.datetime.now()
#                 endtime = experiment.booking.end_time()

#                 boards[key]["board"].setHeat(0)
#                 boards[key]["board"].setFan(100)

#                 log_data(boards[key]["board"], key, experiment.id, 0, 100)
#                 if endtime < now:
#                     boards[key]["experiment_id"] = None
#     except:
#         pass

#     return HttpResponse("")

# def log_data(sbhs, mid, experiment_id, heat=None, fan=None, temp=None):
#     if heat is None:
#         heat = sbhs.getHeat()
#     if fan is None:
#         fan = sbhs.getFan()
#     if temp is None:
#         temp = sbhs.getTemp()

#     data = "%d %s %s %s\n" % (int(time.time()), str(heat), str(fan), str(temp))
#     global_logfile = settings.SBHS_GLOBAL_LOG_DIR + "/" + str(mid) + ".log"
#     with open(global_logfile, "a") as global_loghandler:
#         global_loghandler.write(data)

# def validate_log_file(req):
#     import hashlib
#     data = req.POST.get("data")
#     data = data.strip().split("\n")
#     clean_data = ""
#     for line in data:
#         columns = line.split(" ")
#         if len(columns) >= 6:
#             clean_data += (" ".join(columns[0:6]) + "\n")

#     checksum = hashlib.sha1(clean_data).hexdigest()

#     try:
#         e = Experiment.objects.get(checksum=checksum)
#         return HttpResponse("TRUE")
#     except:
#         return HttpResponse("FALSE")


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
        board_check = map_sbhs_to_rpi(request.META["SERVER_NAME"])
        board = Board()
        all_mac_ids = []
        for machines in board_check:
            all_mac_ids.extend(machines["mac_ids"])
        board.switch_off_inactive_boards(all_mac_ids)
        context["all_boards"] = Board.objects.all()
        return render(request, 'dashboard/show_all_boards.html', context)

@login_required
def profile(request, mid):
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        try:
            filename = settings.SBHS_GLOBAL_LOG_DIR + "/" + str(mid) + ".log"
        except:
            raise Http404("Log does not exist for this profile.")

        delta_T = 1000
        data = subprocess.check_output("tail -n {0} {1}".format(
                                            delta_T, filename
                                            ), 
                                            shell=True)
        data = data.split("\n".encode())
        
        heatcsv = ""
        fancsv = ""
        tempcsv = ""

        plot = []
        for t in range(len(data)):
            line = data[t].decode("utf-8")
            entry = line.strip().split(" ")
            try:
                plot.append([int(float(i)) for i in entry[0:-1] \
                                                        + [float(entry[-1])]])
                heatcsv += "{0},{1}".format(t+1, entry[1])
                fancsv += "{0},{1}".format(t+1,entry[2])
                tempcsv += "{0},{1}".format(t+1, entry[3])
            except:
                continue

        plot = zip(*plot)
        context["mid"] = mid
        context["delta_T"] = delta_T
        context["heat"] = heatcsv
        context["fan"] = fancsv
        context["temp"] = tempcsv
        
    return render(request,"dashboard/profile.html",context)

@login_required
def download_log(request, mid):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        try:
            global_logfile = settings.SBHS_GLOBAL_LOG_DIR + "/" + str(mid) \
                                                                + ".log"
            f = open(global_logfile,'r')
            data = f.read()
            f.close()
            return HttpResponse(data, content_type='text/text')
        except:
            return HttpResponse("Requested log file does not exist")

def zipdir(path,ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root,file))

@login_required
def logs_folder_index(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        if os.path.exists('Experiments.zip'):
            os.remove('Experiments.zip')

        with zipfile.ZipFile('Experiments.zip','w',zipfile.ZIP_DEFLATED) as zipf:
            path = settings.BASE_DIR + '/experiments/'
            zipdir(path,zipf)
        
        with open('Experiments.zip','rb') as stream:
            response = HttpResponse(stream, 
                        content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="{0}"'\
                                                .format('Experiments.zip')
            return response

@login_required
def all_bookings(request):
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        all_bookings = Slot.objects.all().order_by("-start_time")
        paginator = Paginator(all_bookings, 20)
        page = request.GET.get('page')
        try:
            slots = paginator.page(page)
        except PageNotAnInteger:
            slots = paginator.page(1)
        except EmptyPage:
            slots = paginator.page(paginator.num_pages)
        context["slots"] = slots
    return render(request,'dashboard/all_bookings.html', context)    



@login_required
def all_boards(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return render(request,'dashboard/all_boards.html')


@login_required        
def all_images(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return render(request,'dashboard/all_images.html')

@login_required
def test_boards(request):
    user = request.user
    now = timezone.now()
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        boards = Board.objects.filter(online=True)
        context["boards"] = boards
        context["now"] = now
        return render(request,'dashboard/test_boards.html',context)

def user_exists(username):
    try:
        user = User.objects.get(username=username)
    except:
        Http404("User by username: {} does not exists".format(username))

@login_required
def update_mid(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        try:
            username = request.POST.get("username")
            board_id = request.POST.get("board_id")
        except:
            raise Http404("Invalid Parameters")
        user = user_exists(username)
        if user is not None:
            # board = user.userboard_set.all()
            # board.mid = board_id
            # board.save()

            return messages.success("Mid updated successfully")
        else:
            raise Http404("Username: {} does not exists".format(username))

    return redirect(reverse('get_allocated_mids'))

@login_required
def get_allocated_mids(request):
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        pass
        return render(request, 'dashboard/update_mid.html',context)

@login_required
def fetch_logs(request):
    user = request.user
    context = {}
    now = datetime.now()
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        if request.method == 'POST':
            form = FilterLogsForm(request.POST)
            if form.is_valid():
                start_date = form.data["start_time"]
                end_date = form.data["end_time"]
                if start_date and end_date:
                    ys,ms,ds = [int(x) for x in start_date.split('-')]
                    ye,me,de =[int(x) for x in end_date.split('-')]
                slot = Slot.objects.filter(
                        start_time__date__gte=date(ys,ms,ds), 
                        end_time__date__lte=date(ye,me,de)
                        )
                experiment = Experiment.objects.filter(slot__in=slot)
                context["experiments"] = experiment
        else:
            form=FilterLogsForm()
        context['form']=form
    return render(request,'dashboard/fetch_logs.html',context)

def download_file(request, experiment_id):
    experiment = Experiment.objects.get(id=experiment_id)
    response = HttpResponse(content_type='application/text')
    response['Content-Disposition'] = 'attachment; filename={0}'.format(
                                        experiment.log
                                            )
    response.write(open("{0}/{1}".format(settings.MEDIA_ROOT,
                                         experiment.log)
                   ).read())
    return response

@login_required
def turn_on_all_boards(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return HttpResponseRedirect(reverse('moderator_dashboard')) 

@login_required
def turn_off_all_boards(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return HttpResponseRedirect(reverse('moderator_dashboard')) 

@login_required
def book_all_suser_slots(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return HttpResponseRedirect(reverse('moderator_dashboard')) 
