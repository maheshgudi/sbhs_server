try:
	from string import letters
except ImportError:
	from string import ascii_letters as letters
from string import digits, punctuation

from django import forms
from sbhs_server import settings
from django.utils import timezone
from django.contrib.auth.models import User


from .models import Profile, Slot, UserBoard
from .send_emails import generate_activation_key

UNAME_CHARS = letters + "._" + digits
PWD_CHARS = letters + punctuation + digits


class UserLoginForm(forms.Form):
	"""
	User loginform
	"""
	username = forms.CharField(max_length=30)
	password = forms.CharField(max_length=30, widget=forms.PasswordInput())


class UserRegistrationForm(forms.Form):
	name = forms.CharField(max_length=50)
	email = forms.EmailField()
	username = forms.CharField(max_length=30,help_text='Letters, digits, period \
					and underscores only.')
	
	password = forms.CharField(max_length=30, widget=forms.PasswordInput())
	confirm_password = forms.CharField(
		max_length=30, widget=forms.PasswordInput()
	)
	roll_number = forms.CharField(max_length=30, help_text="Use a dummy if \
						you don't have")
	institute = forms.CharField(max_length=128, help_text="Institute/\
						Organization.")
	department = forms.CharField(max_length=64, help_text="Department you \
						work/study at.")
	position = forms.CharField(max_length=64, help_text="Student/Faculty/\
						Researched/Industry/Fellowship/etc.")

	def clean_username(self):
		u_name = self.cleaned_data["username"]
		if u_name.strip(UNAME_CHARS):
			msg = "Only letters, digits, period and underscore characters are \
				allowed in username"
			raise forms.ValidationError(msg)
		try:
			User.objects.get(username__exact=u_name)
			raise forms.ValidationError("Username already exists")
		except User.DoesNotExist:
			return u_name

	def clean_password(self):
		pwd = self.cleaned_data['password']
		if pwd.strip(PWD_CHARS):
			raise forms.ValidationError("Only letters, digits and punctuation \
					are allowed in password")

		return pwd

	def clean_confirm_password(self):
		c_pwd = self.cleaned_data['confirm_password']
		pwd = self.data['password']
		if c_pwd != pwd:
			raise forms.ValidationError("Passwords do not match")

		return c_pwd


	def clean_email(self):
		user_email = self.cleaned_data['email']
		if User.objects.filter(email=user_email).exists():
			raise forms.ValidationError("This email already exists")
		return user_email

	def save(self):
		u_name=self.cleaned_data["username"]
		u_name = u_name.lower()
		pwd = self.cleaned_data["password"]
		email = self.cleaned_data["email"]
		new_user = User.objects.create_user(u_name,email,pwd)
		new_user.name = self.cleaned_data["name"]
		new_user.save()

		cleaned_data = self.cleaned_data
		new_profile = Profile(user=new_user)
		new_profile.roll_number = cleaned_data["roll_number"]
		new_profile.institute = cleaned_data["institute"]
		new_profile.department = cleaned_data["department"]
		new_profile.position = cleaned_data["position"]

		if settings.IS_DEVELOPMENT:
			new_profile.is_email_verified = True
		else:
			new_profile.activation_key = generate_activation_key(
				new_user.username
			)
			new_profile.key_expiry_time = timezone.now() + timezone.timedelta(
				minutes=20
			) 
		new_profile.save()
		return u_name, pwd, new_user.email, new_profile.activation_key


class SlotCreationForm(forms.ModelForm):
	class Meta:
		model = Slot
		fields = ['start_time']
		widgets = {
			'start_time':forms.DateInput(attrs={
				'class':'datetimepicker'
			}),
		}
		
class FilterLogsForm(forms.ModelForm):
	class Meta:
		model = Slot
		
		fields = ['start_time','end_time']
		widgets = {
			'start_time':forms.DateInput(attrs={
					'class':'datetimepicker',
					'name': 'start_date',
					'readonly':'readonly'
				}),
			'end_time':forms.DateInput(attrs={
					'class':'datetimepicker',
					'name':'end_date',
					'readonly':'readonly'
				}),
		}

class UserBoardForm(forms.ModelForm):
	def save(self):
		user = self.cleaned_data["user"]
		board = self.cleaned_data["board"]
		user_board = UserBoard.objects.get(user=user)
		user_board.board = board
		user_board.save()


	class Meta:
		model = UserBoard
		fields = ["user", "board"]
