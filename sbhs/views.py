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

from .models import Board, Experiment, Profile, Slot#, Webcam
from .forms import UserLoginForm, UserRegistrationForm, SlotCreationForm
from . import sbhs
from .send_emails import send_user_mail
from sbhs_server import credentials as credentials

from sbhs.decorators import email_verified
from . import switch_off
from . import switch_onn


LIMIT = 2
# ser = serial.Serial('/dev/ttyUSB0')

# required for experiment views
currentdir = os.path.dirname(
				os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)


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
	

################## Moderator Views ##########################

@login_required
def dashboard_index(request):
	context = {}
	return render(request,'dashboard/dashboard_index.html',context)

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