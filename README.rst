SINGLE BOARD HEATER SYSTEM
==========================

INSTALLATION GUIDE
~~~~~~~~~~~~~~~~~~

1. Clone from the SBHS Github server ::
 https://github.com/CruiseDevice/sbhs_server

2. Create a virtual environment, using command `virtualenv` and activate
   the virtualenv. We recommend using Python 3::
virtualenv myenv -p python3
source myenv/bin/activate

3. Install necessary packages from requirements.txt using command::
     pip install -r requirements.txt

4. Add ``'crispy_forms'`` to INSTALLED_APPS in ``settings.py``

5. Make first migrations by using the commands ::
     python manage.py makemigrations
     python manage.py migrate

6. Create superuser by using the command ::
    python manage.py createsuperuser

    Enter the admin ``username`` and ``email`` you want, then enter the admin
    ``password``.

7. Create moderator group by using command ::
    python manage.py create_moderator

8. Please fill in the necessary information in the file
   ``sbhs_server/credentials.py``.

9. In ``sbhs_server/settings.py``, fill in the following details -

   a. If SBHS devices are connected to a cluster of Raspberry Pis
      or other similar machines, enter the raspberry pi IPs in the
      variable ``RASP_PI_IP``. 

   b. If the SBHS devices are connected directly to the main server through
      USB, Keep ``RASP_PI_IP`` empty and the server will detect devices
      automatically.

10. Run the server by using the command ::
    python manage.py runserver

11. Once the server is running successfully, go to the URL ``http://localhost:8000/account/enter/``

    To create a normal user, just fill the registration form and submit. You can
    the login with the created normal user.

    To create a moderator ::
      * First create a normal user by filling the registration form and submitting
        it
      * Then go to django admin by entering URL ``http://localhost:8000/admin``
      * Login into admin my using credentials you entered while creating admin
        in ``step ?``
      * Go to the ``profile`` section and click on the user you just created.
      * Tick is_moderator checkbox and click on save.
      * Exit the admin by loggin out of it.

    Now you have created a moderator account. With moderator account you can
    view state of all the SBHS connected, all the logs of the all the users,
    all the slots booked by the users, and also the profile of each SBHS.

