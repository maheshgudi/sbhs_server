import os
import sys
import time
import json
import random
import zipfile
import inspect
import pytz
import requests
import subprocess, zipfile
from textwrap import dedent
from time import gmtime, strftime
import time as tm
from datetime import datetime as dt, timedelta, date, time

from django.urls import reverse
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth.models import User
from django.contrib import messages
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.six import python_2_unicode_compatible
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.http import HttpResponse, HttpResponseRedirect,\
    Http404, HttpResponseServerError, JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


from .models import Board, Experiment, Profile, Slot, UserBoard, Webcam
from .forms import (
    UserLoginForm, UserRegistrationForm, SlotCreationForm, FilterLogsForm,
    UserBoardForm
    )
from .send_emails import send_user_mail
from sbhs_server import credentials as credentials
from sbhs.decorators import email_verified


################# pages views #######################

def index(request, next_url=None):
    """
    Index page of Website.
    """
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
    """
    Checks if the user is authenticated
    Assign the board to user when he first logins in a random order.
    If not authenticated redirect back to LoginForm.
    """
    user = request.user
    if user.is_authenticated():
        if not UserBoard.objects.filter(user=user).exists():
            if Board.objects.all().exists():
                user_board = random.choice(Board.objects.filter(
                                           online=True
                                            )
                                           )
                UserBoard.objects.create(user=user, board=user_board)
            else:
                raise Http404("Could not find any SBHS devices connected.")
        return render(request,'account/home.html')

    return render(request,'account/account_index.html',{
        'login_form':UserLoginForm(request.POST or None),
        'registration_form':UserRegistrationForm(request.POST or None)    
    })

def user_login(request):
    """
    Logs in existing user
    Generates alerts if:
        Either username or password do not match.
        If the account is disabled or not activated yet.
    """
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
    """
    Logs out a logged-in user
    """
    logout(request)
    return redirect('account_enter')

def user_register(request):
    """
    Create new user:
    Generates activation key and sends it to users registered email id.
    """
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

def activate_user(request, key):
    """
    Verify user account from the generated activation key user received
    in his mail.
    """
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
    """
    User requests for new_activation key incase if the first activation
    key expires
    """
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

def update_email(request):
    """
    Updates user email_id
    """
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
    """
    Books a new slot for the user:

    Shows all booked slots
        Shows users alerts if:

            Slot is successfully booked
            User exceeds the limit of number of slots that can be
            booked in advance for a day.

            Requested slot is already booked by another user.

    Deletes a previouslt booked slot:
        Booked slot is deleted successfully.
        Slot cannot be deleted if it expires.
    """
    user = request.user
    board = UserBoard.objects.filter(user=user).order_by("id").last()
    if board:
        all_board_users = board.get_all_users_for_board()
        all_board_users_id = [i.user.id for i in all_board_users]
    else:
        all_board_users_id = []
    slot_history = Slot.objects.filter(user=user).order_by("-start_time") 
    context = {}
    now = timezone.now()
    current_slot = slot_history.filter(start_time__lt=now, end_time__gte=now)
    board_all_booked_slots = Slot.objects.board_all_booked_slots(
                                board.board.mid
                                )
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

                new_slot_date = new_slot.start_time.date()
                new_slot_time = new_slot.start_time.time()
                new_slot_date_slots = slot_history.filter(
                                        start_time__date=new_slot_date
                                        )
                if len(new_slot_date_slots) >= settings.LIMIT:
                    messages.warning(request,'Cannot Book more than {0} \
                        slots in advance in a day'.format(settings.LIMIT))
                else:
                    if Slot.objects.check_booked_slots(
                        new_slot.start_time, all_board_users_id):

                        if new_slot.start_time >= now:
                            new_slot.start_time = dt.combine(
                                       new_slot.start_time.date(),
                                       time(new_slot.start_time.hour,00)
                                       )
                            new_slot.end_time = dt.combine(
                                       new_slot.start_time.date(),
                                       time(new_slot.start_time.hour,
                                            settings.SLOT_DURATION
                                            )
                                       )
                            new_slot.user = user
                            new_slot.save()
                            messages.success(request,
                                             'Slot created successfully.'
                                             )
                        else:
                            messages.error(request,
                                             'Start time selected'
                                             + ' is before today.'
                                             + 'Please choose again.'
                                            )
                    else:
                        messages.error(request,
                                       'Slot is already booked.'
                                     + ' Try the next slot.'
                                    )

        if request.POST.get("book_now") == "book_now":
            if not current_slot:
                if  Slot.objects.check_booked_slots(
                                 now, all_board_users_id):
                    slot_now = Slot.objects.create(
                                user=user,
                                start_time=dt.combine(now.date(),
                                           time(now.hour,00)),
                                end_time=dt.combine(now.date(),
                                   time(now.hour, settings.SLOT_DURATION)
                                   )
                                )
                    messages.success(request,'Slot created successfully.')
                else:
                    messages.error(request,
                                   'Slot is booked by someone else.'
                                 + ' Try the next slot.'
                                )
            else:
                messages.error(request,'Slot is already booked for \
                                current time. Please select a future slot.'
                                )
        return redirect("slot_new")

    else:
        form = SlotCreationForm()
        context['history']=slot_history
        context['form']=form
        context['now'] = now
        context['board_all_booked_slots'] = board_all_booked_slots
    return render(request,'slot/create_slot.html',context)
    


###################Experiment Views ######################

def check_connection(request):
    """
    Check connection if it exists or not with the Client App .
    """
    return HttpResponse("TESTOK")

def client_version(request):
    """
    Returns client version
    """
    return HttpResponse(str(settings.CLIENT_VERSION))

   
@csrf_exempt
def initiation(request):
    """

    """
    username = request.POST.get("username")
    password = request.POST.get("password")
    user = authenticate(username=username, password=password)
    if user:
        login(request, user)
        if user.is_active:
            now = timezone.now()
            slots = Slot.objects.get_user_slots(user).order_by("id")
            slot = slots.last()
            board = UserBoard.objects.get(user=user).board
            check_status_path = "reset/{0}".format(board.usb_id)
            check_status = connect_sbhs(board.raspi_path, check_status_path)
            if check_status["status"] and slot:
                filename = dt.strftime(now, "%Y%b%d_%H_%M_%S.txt")
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

def map_sbhs_to_rpi():
    """
    Scans if the machine are connected to the rpis.
    If the machines are connected map them with their specific rpis.
    """
    r_pis = settings.SBHS_API_IPS
    map_machines = []
    dead_machines = []
    rpi_map = {}
    if r_pis:
        for r_pi in r_pis:
            rpi_map["rpi_ip"] = r_pi
            try:
                mac_ids = connect_sbhs(r_pi, "get_machine_ids")
                for devices in mac_ids:
                    board = Board()
                    board.save_board_details(r_pi, devices)
                rpi_map["mac_ids"] = [i['sbhs_mac_id'] for i in mac_ids]
                map_machines.append(rpi_map.copy())
            except:
                dead_machines.append(r_pi)
    return map_machines, dead_machines

def connect_sbhs(rpi_ip, experiment_url):
    connect_rpi = requests.get("http://{0}/experiment/{1}".format(
                           rpi_ip, experiment_url), timeout=5
                        )
    data = json.loads(connect_rpi.text)
    return data

@login_required
@csrf_exempt
def experiment(request):
    try:
        user = request.user
        server_start_ts = int(tm.time() * 1000)
        slot = Slot.objects.get_user_slots(user)\
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

                server_end_ts = int(tm.time() * 1000)

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
    """
    Update the experimental log file.
    """
    data = "{0} {1} {2} {3}\n".format(int(tm.time()),str(heat),
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
    """
    Renders experimental log files to the user interface.
    """
    user = request.user
    context = {}
    all_bookings = Slot.objects.filter(user__username=user)
    all_booking_ids = [booking.id for booking in all_bookings]
    experiment = Experiment.objects.select_related("slot")\
                    .filter(slot_id__in=all_booking_ids)
    for exp in experiment:
        exp.logname = exp.log.split("/")[-1]
        context['exp.logname'] = exp.logname 
    context['experiment'] = experiment
    return render(request,'experiment/logs.html',context)

@login_required
def download_user_log(request, experiment_id):
    """
    download logs related to the user
    """
    user = request.user
    experiment_data = Experiment.objects.get(slot__id=experiment_id)
    f = open(os.path.join(settings.EXPERIMENT_LOGS_DIR, experiment_data.log),"r")
    data = f.read()
    f.close()
    return HttpResponse(data, content_type="text/text")
    

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
            filename = settings.SBHS_GLOBAL_LOG_DIR + "/" + mid + ".log"
            f = open(filename, "r")
            f.close()
        except:
            raise Http404("Log does not exist for this profile.")

        delta_T = 1000
        data = subprocess.check_output("tail -n {0} {1}".format(
                                            delta_T, filename
                                            ), 
                                            shell=True)

        data = data.split("\n".encode())
        
        plot = []
        heatcsv = ""
        fancsv = ""
        tempcsv = ""

        for t in range(len(data)):
            line = data[t].decode("utf-8")
            entry = line.strip().split(" ")
            try:
                plot.append([int(float(i)) for i in entry[0:-1] \
                                                        + [float(entry[-1])]])
                heatcsv += "{0},{1}\\n".format(t+1, entry[1])
                fancsv += "{0},{1}\\n".format(t+1,entry[2])
                tempcsv += "{0},{1}\\n".format(t+1, entry[3])
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
    """
    Download logs related to the user
    """
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
    """
    Compress the experiments directory and download.
    """
    user = request.user
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        if os.path.exists('Experiments.zip'):
            os.remove('Experiments.zip')

        with zipfile.ZipFile('Experiments.zip','w',zipfile.ZIP_DEFLATED) \
                as zipf:
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
    """
    Show all the bookings by all the users
    """
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
def all_images(request):
    user = request.user
    context = {}
    image_links = []
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        boards = Board.objects.filter(online=True)
        for board in boards:
            board_image_link = {}
            capture_status = Webcam.load_image(board.mid)
            board_image_link["board"] = board
            if capture_status != 0:
                board_image_link["image_link"] = board.image_link()
            image_links.append(board_image_link.copy())
        context["image_links"] = image_links
        return render(request,'dashboard/all_images.html', context)


@login_required
def update_board_values(request, mid):
    if request.method == 'POST':
        heat = request.POST.get('set_heat', None)
        fan = request.POST.get('set_fan', None)
        device = Board.objects.get(mid=mid)
        if heat and fan:
            set_heat = connect_sbhs(device.raspi_path,
                                "set_heat/{0}/{1}".format(device.usb_id, heat)
                                )
            set_fan = connect_sbhs(device.raspi_path,
                                "set_fan/{0}/{1}".format(device.usb_id, fan)
                                )
            if not (set_fan["status"] or set_heat["status"]):
                messages.error(request, "Could not set heat and for board {}"\
                         .format(board.mid))


    return redirect("test_boards")

@login_required
def test_boards(request):
    """
    Test boards from the Web interface.
    """
    user = request.user
    now = timezone.now()
    context = {}
    dead_servers = []
    boards = Board.objects.filter(online=True)
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        if request.POST.get("update_boards") == "update_boards":
            board_check, dead_servers = map_sbhs_to_rpi()
            board = Board()
            all_mac_ids = []
            for machines in board_check:
                all_mac_ids.extend(machines["mac_ids"])
            board.switch_off_inactive_boards(all_mac_ids)

        if request.POST.get("reset_all") == "reset_all":
            for board in boards:
                try:
                    resp = connect_sbhs(board.raspi_path,"reset/{0}".format(
                                      board.usb_id
                                      )
                                      )
                except requests.exceptions.ConnectionError:
                    if device.raspi_path not in dead_servers:
                        dead_servers.append(device.raspi_path)

        all_devices = []
        for device in boards:
            devices = {}
            try:
                temp = connect_sbhs(device.raspi_path,
                                   "get_temp/{0}".format(device.usb_id)
                                    )
            except requests.exceptions.ConnectionError:
                if device.raspi_path not in dead_servers:
                    dead_servers.append(device.raspi_path)
            devices["board"] = device
            devices["temp"] = temp
            all_devices.append(devices)
        context["all_devices"] = all_devices
        if dead_servers:
            context["dead_servers"] = dead_servers
        return render(request,'dashboard/test_boards.html',context)

def user_exists(username):
    try:
        user = User.objects.get(username=username)
    except:
        Http404("User by username: {} does not exists".format(username))

@login_required
def update_mid(request):
    """
    Update mid given to user.
    """
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to see this page.")
    else:
        if request.method == 'POST':
            if request.POST.get("update_mid") == "update_mid":
                form = UserBoardForm(request.POST)
                if form.is_valid():
                    form.save()

        context["form"]= UserBoardForm()
    return render(request, 'dashboard/update_mid.html',context)

@login_required
def fetch_logs(request):
    """
    fetch logs in between the given dates.
    """
    user = request.user
    context = {}
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
                    if slot:
                        experiment = Experiment.objects.filter(slot__in=slot)
                        context["experiments"] = experiment
        else:
            form=FilterLogsForm()
        context['form']=form
    return render(request,'dashboard/fetch_logs.html',context)

def download_file(request, experiment_id):
    try:
        experiment = Experiment.objects.get(id=experiment_id)
        response = HttpResponse(content_type='application/text')
        response['Content-Disposition'] = 'attachment; filename={0}'.format(
                                            experiment.log
                                                )
        response.write(open("{0}/{1}".format(settings.MEDIA_ROOT,
                                             experiment.log)
                       ).read())
        return response
    except FileNotFoundError as fnfe:
        raise fnfe


################## Webcam Views #############################

@login_required
def show_video(request):
    """
    Show the video of the SBHS.
    """
    user = request.user
    context = {}
    board = UserBoard.objects.filter(user=user).order_by("id").last()
    if board:
        image_link = board.board.image_link()
        context["image_link"] = image_link
    context["mid"] = board.board.mid
    return render(request, 'webcam/show_video.html',context)

@login_required
def show_video_to_moderator(request,mid):
    """
    Shows the video of all the SBHSs to the moderator.
    """
    user = request.user
    context = {}
    if not is_moderator(user):
        raise Http404("You are not allowed to view this page.")
    else:
        board = Board.objects.filter(mid=mid).order_by("id").last()
        if board:
            image_link = board.image_link()
            context["image_link"] = image_link
        context["mid"] = mid
        return render(request, 'webcam/show_video.html',context)
