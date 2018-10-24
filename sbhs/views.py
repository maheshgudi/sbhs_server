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
            board = Board()
            board.save_board_details(r_pi, mac_ids)
            rpi_map["mac_ids"] = [i['sbhs_mac_id'] for i in mac_ids]
            map_machines.append(rpi_map)
    else:
        rpi_map = {}
        client_name = client_ip + ":1234"
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
            print(filename)
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
        slot_history = Slot.objects.all().order_by("-start_time")
        context["boards"] = boards
        context["slot_history"] = slot_history[0]
        context["now"] = now
        return render(request,'dashboard/test_boards.html',context)

@login_required
def update_mid(request):
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        return render(request,'dashboard/update_mid.html')

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
