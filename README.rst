SINGLE BOARD HEATER SYSTEM
==========================

INSTALLATION GUIDE
~~~~~~~~~~~~~~~~~~

1. Clone from github server - https://github.com/CruiseDevice/sbhs_server
2. Create a virtual environment, using command `virtualenv` and activate
   the virtualenv. We recommend using Python 3.::
        virtualenv myenv -p python3
        source myenv/bin/activate

3. Install necessary packages from requirements.txt using command::
     pip install -r requirements.txt
4. Make first migrations by using the commands ::
     python manage..py makemigrations
     python manage..py migrate
5. Please fill in the necessary information in the file
   ``sbhs_server/credentials.py``.
6. In ``sbhs_server/settings.py``, fill in the following details -
   a. If SBHS devices are connected to a cluster of Raspberry Pis
      or other similar machines, enter the raspberry pi IPs in the
      variable ``RASP_PI_IP``. 
