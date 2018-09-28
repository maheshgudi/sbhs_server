import serial
import os
from time import localtime, strftime, sleep
# import credentials
import sbhs_server.credentials as credentials

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
        self.out_max_fan = 100

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
            self.sbhs = self.get_machine_id()
            # org stopbits = 1
            status = True
        except Exception as e:
            status = False
            print(e)
        return status

    def map_sbhs_to_usb(self, usb_devices):
        sbhs_map = []
        if usb_devices:
            for usb in usb_devices:
                print("usb", usb)
                status = self.connect_device(usb)
                if status:
                    sbhs = self.sbhs
                    sbhs_map.append({"usb_id": usb, "sbhs_mac_id": sbhs})
        return sbhs_map

    def connect(self, machine_id):
        """ 
        Open a serial connection via USB to the SBHS using the 
        machine id 
        """
        # check for valid machine id number
        try:
            self.machine_id = int(machine_id)
        except:
            return False

        # get the usb device file from the machine map file
        try:
            map_file = open(MAP_FILE, 'r')
            usb_device_file = False

            for mapping_str in map_file.readlines():
                mapping = mapping_str.split('=')
                self.log('mapping: ' + mapping[1], 'ERROR') #srikant

                # if mapping for the machine id found set the usb device 
                # file and break out of loop
                if mapping[0] == str(self.machine_id):
                    usb_device_file = mapping[1].strip()
            #self.log('usb_device_file: ' + usb_device_file, 'ERROR') #srikant
                    break
            
            # reached end of file and check if machine id entry is present 
            # in the machine map file
            map_file.close()
            if not usb_device_file:
                print("Error: cannot locate the USB device in the map table \
                         for machine id {}".format(self.machine_id))
                self.log('cannot locate the USB device in the map table for \
                            machine id %d' % self.machine_id, 'ERROR')
                return False
        except:
            # map_file.close()
            print("Error: cannot get the USB device path for the machine \
                    id {}".format(self.machine_id))
            self.log('cannot get the USB device path for the machine id\
                        %d' % self.machine_id, 'ERROR')
            return False

        # check if SBHS device is connected
        if not os.path.exists(usb_device_file):
            print("SBHS device file" +usb_device_file + "does not exists")
            self.log('SBHS device file ' + usb_device_file + ' does not\
                         exists', 'ERROR')
            return False
        try:
            self.boardcon = serial.Serial(port=usb_device_file, \
                                baudrate=9600, bytesize=8, parity='N', \
                                stopbits=1, timeout=2) #orignal stopbits = 1
            self.status = 1
            return True
        except serial.serialutil.SerialException:
            print("Error: cannot connect to machine id \
                     {}".format(self.machine_id))
            self.log('cannot connect to machine id \
                         %d' % self.machine_id, 'ERROR')
            
            self.machine_id = -1
            self.device_num = -1
            self.boardcon = False
            self.status = 0


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

    def setFan(self, val):
        """ Sets the fan speed, checks if value is valid i.e. within range.
            Input: self object, val
            Output: Error message if fan cannot be set.
        """
        if val > MAX_FAN or val < 0:
            print("Error: fan value cannot be more than {}".format(MAX_FAN))
            return False
        try:
            self._write(chr(INCOMING_FAN))
            sleep(0.5)
            self._write(chr(val))
            return True
        except:
            print("Error: cannot set fan for machine id \
                    {}".format(self.machine_id))
            self.log('cannot set fan for machine id %d' % self.machine_id, \
                        'ERROR')
            return False

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
            self._write(str(self.outgoing_machine_id).encode())
            sleep(0.5) 
            machine_id = self._read(1)
        except Exception as e:
            print("e-->", e)
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
            data = self.boardcon.read(size).decode("ascii")
            print(data)
            return data
        except Exception as e:
            print(e)

    def _write(self, data):
        try:
            self.boardcon.write(data)
            return True
        except Exception as e:
            print(e)

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


# if no device filename found then exit
# for device in device_files:
#     s = sbhs.Sbhs()
#     # getting the number from the device filename
#     dev_id = device[6:]
#     try:
#         dev_id = int(dev_id)
#     except:
#         print('Invalid device name /dev/%s' % device)
#         continue
#     # connect to device
#     res = s.connect_device(dev_id)
#     if not res:
#         print ('Cannot connect to /dev/%s' % device)
#         s.disconnect()
#         continue
#     # get the machine id from the device
#     machine_id = s.getMachineId()
#     if machine_id < 0:
#         print('Cannot get machine id from /dev/%s' % device)
#         s.disconnect()
#         continue
#     print ('Found SBHS device /dev/%s with machine id %d' % (device, machine_id))
#     map_str = "%d=/dev/%s\n" % (machine_id, device)
#     map_machine_file.write(map_str)

# print ('Done. Exiting...')
# map_machine_file.close()
# sys.exit(1)

