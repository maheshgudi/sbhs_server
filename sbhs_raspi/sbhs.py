import serial
import os
from time import localtime, strftime, sleep

# MAP_FILE = credentials.MAP_FILE
#LOG_FILE = '../log/sbhserr.log'
# LOG_FILE = credentials.LOG_FILE

class SbhsServer(object):
    """ This is the Single Board Heater System class """

    def __init__(self):
        self.outgoing_machine_id = 252
        self.incoming_fan = 253
        self.incoming_heat = 254
        self.outgoing_temp = 255
        self.max_heat = 100
        self.max_fan = 100

    def get_usb_devices(self):
        usb_devices = []
        for tty in os.listdir('/dev'):
            if tty.startswith('ttyUSB'):
                try:
                    usb_devices.append(int(tty[6:]))
                except ValueError:
                    pass
        return usb_devices

    def connect_device(self, device_num):
        """ 
        Open a serial connection via USB to the SBHS using USB Device Number
        """
        # check for valid device number
            
        usb_device_file = '/dev/ttyUSB{}'.format(device_num)
        try:
            self.boardcon = serial.Serial(port=usb_device_file,
                                          baudrate=9600, bytesize=8,
                                          parity='N', stopbits=1,
                                          timeout=2
                                          )
            # org stopbits = 1
            status = True
        except Exception as e:
            status = False
        return status

    def map_sbhs_to_usb(self, usb_devices):
        sbhs_map = []
        if usb_devices:
            for usb in usb_devices:
                print("usb", usb)
                status = self.connect_device(usb)
                if status:
                    sbhs = self.get_machine_id()
                    sbhs_map.append({"usb_id": usb, "sbhs_mac_id": sbhs})
        return sbhs_map


    def setHeat(self, val):
        """ Sets the heat, checks if value is valid i.e. within range.
            Input: self object, val
            Output: Error message if heat cannot be set.
        """
        if val > MAX_HEAT or val < 0:
            print("Error: heat value cannot be more than {}".format(MAX_HEAT))
            return False

        try:
            self._write(chr(INCOMING_HEAT))
            sleep(0.5)
            self._write(chr(val))
            return True
        except:
            print("Error: cannot set heat for machine \
                    id {}".format(self.machine_id))
            self.log('cannot set heat for machine id \
                        %d' % self.machine_id, 'ERROR')
            return False

    def set_fan(self, val):
        """ Sets the fan speed, checks if value is valid i.e. within range.
            Input: self object, val
            Output: Error message if fan cannot be set.
        """
        if val > self.out_fan or val < 0:
            return False
        try:
            self._write(chr(self.incoming_fan))
            sleep(0.5)
            self._write(chr(val))
            return True
        except:
            return True

    def getTemp(self):
        """ Gets the temperature from the machine.
        """
        try:
            self.boardcon.flushInput()
            self._write(chr(OUTGOING_TEMP))
            temp = ord(self._read(1)) + (0.1 * ord(self._read(1)))
            return temp
        except:
            print("Error: cannot read temperature from machine id \
                    {}".format(self.machine_id))
            self.log('cannot read temperature from machine id %d' \
                        % self.machine_id, 'ERROR')
        return  0.0

    def get_machine_id(self):
        """ Gets machine id from the device """
        try:
            self.boardcon.flushInput()
            self._write(chr(self.outgoing_machine_id))
            sleep(0.5) 
            machine_id = ord(self._read(1))
        except Exception as e:
            machine_id = -1
        return int(machine_id)

    def disconnect(self):
        """ Reset the board fan and heat values and close the USB connection """
        try:
            self.boardcon.close()
            self.boardcon = False
            self.status = 0
            return True
        except:
            print('Error: cannot close connection to the machine')
            self.log('cannot close connection to the machine', 'ERROR')
            return False

    def reset_board(self):
        return self.setHeat(0) and self.setFan(100)

    def _read(self, size):
        try:
            data = self.boardcon.read(size)
            return data
        except Exception as e:
            raise

    def _write(self, data):
        try:
            self.boardcon.write(data)
            return True
        except Exception as e:
            raise

    def log(self, msg, level):
        try:
            errfile = open(LOG_FILE, 'a') # open error log file in append mode
            if not errfile:
                return
            log_msg = '%s %s %s\n' %(level, strftime('%d:%m:%Y %H:%M:%S', \
                        localtime()), msg)  

            errfile.write(log_msg)
            errfile.close()
            return
        except:
            return
