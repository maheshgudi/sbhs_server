import serial
import os
import logging
from time import localtime, strftime, sleep


logging.basicConfig(filename="sbhserr.log",
                    format='%(asctime)s --- %(message)s'
                    )
logger=logging.getLogger()
logger.setLevel(logging.DEBUG)

class SbhsServer(object):
    """ This is the Single Board Heater System class """

    def get_usb_devices(self):
        usb_ids = []
        for tty in os.listdir('/dev'):
            if tty.startswith('ttyUSB'):
                try:
                    usb_ids.append(int(tty[6:]))
                except ValueError:
                    logger.error("Could not get {0}".format(tty))
        return usb_ids

    def map_sbhs_to_usb(self, usb_devices):
        sbhs_map = []
        if usb_devices:
            for usb_id in usb_devices:
                sbhs = Sbhs(dev_id=usb_id)
                status = sbhs.connect_device()
                if status:
                    board = sbhs.get_machine_id()
                    logger.info("USB {0} is connected to SBHS machine id {1}"
                           .format(usb_id, board)
                           )
                    sbhs_map.append({"usb_id": usb_id, "sbhs_mac_id": board})
        return sbhs_map


class Sbhs(object):

    def __init__(self, dev_id):

        self.outgoing_machine_id = 252
        self.incoming_fan = 253
        self.incoming_heat = 254
        self.outgoing_temp = 255
        self.max_heat = 100
        self.max_fan = 100
        self.dev_id = dev_id

    def connect_device(self):
        """ 
        Open a serial connection via USB to the SBHS using USB Device Number
        """
        # check for valid device number
            
        usb_device_file = '/dev/ttyUSB{}'.format(self.dev_id)
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
            logger.error("Serial connection with {0} failed"
                   .format(usb_device_file)
                   )
        return status

    def get_machine_id(self):
        """ Gets machine id from the device """
        try:
            self.boardcon.flushInput()
            self._write(chr(self.outgoing_machine_id))
            sleep(0.5)
            machine_id = ord(self._read(1))
            self.machine_id = machine_id
        except Exception as e:
            machine_id = -1
        return int(machine_id)

    def set_machine_heat(self, val):
        """ Sets the heat, checks if value is valid i.e. within range.
            Input: self object, val
            Output: Error message if heat cannot be set.
        """
        if val > self.max_heat or val < 0:
            logger.error("Machine ID {0} tried setting heat {1}%".format())
            return False

        try:
            self._write(chr(self.incoming_heat))
            sleep(0.5)
            self._write(chr(val))
            return True
        except:
            print("Error: cannot set heat for machine \
                    id {}".format(self.machine_id))
            self.log('cannot set heat for machine id \
                        %d' % self.machine_id, 'ERROR')
            return False

    def set_machine_fan(self, val):
        """ Sets the fan speed, checks if value is valid i.e. within range.
            Input: self object, val
            Output: Error message if fan cannot be set.
        """
        if val > self.max_fan or val < 0:
            return False
        try:
            self._write(chr(self.incoming_fan))
            sleep(0.5)
            self._write(chr(val))
            return True
        except:
            return True

    def get_machine_temp(self):
        """ Gets the temperature from the machine.
        """
        try:
            self.boardcon.flushInput()
            self._write(chr(self.outgoing_temp))
            temp = ord(self._read(1)) + (0.1 * ord(self._read(1)))
            return temp
        except:
            print("Error: cannot read temperature from machine id \
                    {}".format(self.machine_id))
            self.log('cannot read temperature from machine id %d' \
                        % self.machine_id, 'ERROR')
        return  0.0

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
        return self.set_machine_heat(0) and self.set_machine_fan(100)

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
