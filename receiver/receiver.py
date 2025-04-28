from serial import Serial
import time
import threading
from multiprocessing import Queue
from receiver.connection import Connection
from receiver.imu import IMU, MAG_CALI_TIMES

# Default connection type
DEFAULT_CONNECTION_TYPE = 'COM'

# Serial Settings
SERIAL_COM_PORT='COM7'
SERIAL_BAUD_RATE = 921600

#BlueZ Settings
BLUEZ_MAC_ADDRESS = "00:1A:FF:06:5A:27"
BLUEZ_RFCOMM_PORT = 1


# IMU State
STATE_STOP = 0
# STATE_CALIBRATION_ACC = 1
STATE_CALIBRATION_MAG = 2
STATE_READ_DATA = 3

# ESA IMU commands
ESA_CMD_STOP = b'\x00'
ESA_CMD_START = b'\x01'
ESA_CMD_MAG_CAL = b'\x02'



class IMU_Receiver():
    b_ready = True
    state = STATE_CALIBRATION_MAG
    check_debug= False
    use_offset = False
    save_offset = False
    receiving = False
    queue_ready = False
    writing_csv = False
    write_csv = False
    write_raw_csv = False
    set_write_timer = False
#     packet_size = 36
    packet_size = 342

    acc_raw = [0,0,0]
    gyro_raw =[0,0,0]
    mag_raw = [0,0,0]
    time_raw = [0,0,0,0,0]

    time_start = time.time()

    acc = []
    gyro = []
    mag = []
    time = []

    

    # -----------------------------
    # constructor
    def __init__(self, connection_type=DEFAULT_CONNECTION_TYPE, com_port=SERIAL_COM_PORT, baud_rate=SERIAL_BAUD_RATE, mac_address=BLUEZ_MAC_ADDRESS, rfcomm_port=BLUEZ_RFCOMM_PORT, packet_size=36, check_debug=False, use_offset=True, load_offset=False,save_offset=False, offset_path="offset.csv", write_raw_csv=False, raw_csv_path='raw.csv', write_csv=False, csv_path="imu.csv", calibration_callback=lambda acc,gyro,mag,proc,time,delt,cali_times:None, finish_calibration_callback=lambda rec:None, receive_callback=lambda acc,gyro,mag,proc,time,delt,cali_times:None, write_timer_end_callback=lambda rec:None):
        self.connection = Connection(connection_type,mac_address,com_port if connection_type=="COM" else rfcomm_port, baud_rate)
        self.check_debug = check_debug
        self.load_offset = load_offset
        self.save_offset = save_offset
        self.use_offset = use_offset
        self.imu = IMU(use_offset=use_offset,load_mag_offset=load_offset,save_offset=save_offset,offset_file=offset_path)

        self.packet_size = packet_size

        self.calibration_callback = calibration_callback
        self.finish_calibration_callback = finish_calibration_callback
        self.receive_callback = receive_callback
        self.write_timer_end_callback = write_timer_end_callback
        
        self.create_raw_csv(write_raw_csv=write_raw_csv,raw_csv_path=raw_csv_path)
        
        self.create_csv(write_csv=write_csv, csv_path=csv_path)
        
        

    # -----------------------------
    # connect com port
    def com_connect(self):
        # connect
        try:
            self.connection.connect()
        except:
            print("0.1-Com port open fail")
            return False
        
        # send stop
        print("0.1-Com port open success")

        if not self._cmd_write(ESA_CMD_STOP):
            print("0.2-ESA IMU system do not exist")
            self.connection.disconnect()
            return False

        # send start
        print("0.2-ESA IMU system exist")
        if not self._cmd_write(ESA_CMD_START):
            print("0.3-ESA IMU System Start Fail")
            self.connection.disconnect()
            return False
        
        # started
        print("0.3-Start ESA IMU system")
        if self.load_offset or not self.use_offset:
            self.state = STATE_READ_DATA # use prerecorded offset
        else:
            self.state = STATE_CALIBRATION_MAG

        
        

        self.receiving = True
        self.queue_ready = True
        self.queue = Queue()
        # start parse process
        read_thread = threading.Thread(target=self._read_process)
        read_thread.start()   
        parse_thread =  threading.Thread(target=self._parse_process)
        parse_thread.start()
        
        return True


    # -----------------------------
    # connect com port
    def com_disconnect(self):
        # stop receiving
        self.receiving = False
        self.state = STATE_STOP
        time.sleep(1)
        
        # send stop
        if not self._cmd_write(ESA_CMD_STOP):
            print("COM Port already disconnected")
        self.connection.disconnect()



    def close_queue(self):
        self.queue.cancel_join_thread()
        self.queue.close()


    # -----------------------------
    # create csv
    def create_csv(self,write_csv,csv_path):
        self.write_csv = write_csv
        if write_csv:
            print(csv_path)
            self.csv = open(csv_path,'a')
            self._write_csv_header()


    # -----------------------------
    # create raw csv
    def create_raw_csv(self,write_raw_csv,raw_csv_path):
        self.write_raw_csv = write_raw_csv
        if write_raw_csv:
            print(raw_csv_path)
            self.csv_raw = open(raw_csv_path,'a')

    
    
    # -----------------------------
    # start write csv
    def start_write_csv(self, set_write_timer=False, write_time=60.0):
        def writing_timer_process(write_time,callback):
            time.sleep(write_time)
            if self.writing_csv:
                self.stop_write_csv()
                callback(self)


        # remove all items in queue
        if self.state == STATE_READ_DATA:
            while not self.queue.empty():
                self.queue.get()
    
        # set write flag to true
        self.writing_csv = True
        self.set_write_timer = set_write_timer

        if set_write_timer:
            threading.Thread(target=writing_timer_process,args=(write_time,self.write_timer_end_callback,)).start() 


    # stop write csv
    def stop_write_csv(self):
        self.writing_csv = False
        if self.write_csv:
            self.csv.close()

        if self.write_raw_csv:
            self.csv_raw.close()
    

    #-----------------------------
    # UTILITIES

     # -----------------------------
    # write cmd byte to com port
    def _cmd_write(self, cmd):
        cmd_buff = b'\x55'+cmd+b'\x03\x03\x01\x01\x01\x01\x01\x01\xAA'
        try:
            self.connection.send(bytes(cmd_buff))
        except:
            return False
        
        if cmd == ESA_CMD_STOP:
            try:
                self.connection.read(11)
            except:
                return False

        elif cmd == ESA_CMD_START:
            return True
            # try:
            #     self.connection.read(11)
            # except:
            #     return False

        elif cmd == ESA_CMD_MAG_CAL:
            try:
                self.connection.read(11)
            except:
                return False
        return True
    
    # -----------------------------
    # read imu data
    def _read_process(self):
       while self.receiving:
            buffer = self.connection.read(512)
            if len(buffer) >= 1:
                for b in buffer:
                    if self.receiving:
                        self.queue.put(b)

    # --------------------------------
    # parse imu data
    def _parse_process(self):
        data_array = []
        while self.queue_ready:
            if not self.queue.empty():
                byte = self.queue.get()
                # locate header (0x55 0xaa)
                if len(data_array) == 0:
                    if byte == 0x55:
                        data_array.append(byte)
                        continue
                    else:
                        continue

                if len(data_array) == 1:
                    if byte == 0xaa:
                        data_array.append(byte)
                        continue
                    else:
                        data_array = []
                        continue

                # add data to array until reached packet size
                data_array.append(byte)
                
                # reached packet length, process data
                if len(data_array) >= self.packet_size:
                    # print(data_array)
                    if self.state == STATE_READ_DATA and self.writing_csv and self.write_raw_csv:
                        threading.Thread(target=self._write_raw_process, args=(data_array,)).start()
                    
                    # extract data into raw array
                    # for i in range(5):
                    self.acc_raw = data_array[18:24]
                    self.gyro_raw = data_array[24:30]
                    self.mag_raw = data_array[30:36]
                    self.time_raw = data_array[2:7]
                    data_array = data_array[self.packet_size:]
                    # state process
                    self._imu_state_machine()

     # --------------------------------
    # write raw data to csv
    def _write_raw_process(self, data_array):
        line = ",".join([str(n) for n in data_array])
        line += "\n"
        try:
            self.csv_raw.write(line)
        except:
            pass

    # --------------------------------
    # write csv heaser
    def _write_csv_header(self):
        # self.csv.write("Processed,Time(h),Time(m),Time(s),Time(ms),Delt,AccX,AccY,AccZ,GyroX,GyroY,GyroZ,MagX,MagY,MagZ,Roll,Pinch,Yaw,PCTimestamp\n")
        self.csv.write("Processed,Time(h),Time(m),Time(s),Time(ms),Delt,AccX,AccY,AccZ,GyroX,GyroY,GyroZ,MagX,MagY,MagZ,PCTimestamp\n")

    # --------------------------------
    # state
    def _imu_state_machine(self):
        if self.state == STATE_CALIBRATION_MAG:
            # mag calibration
            self.imu.set_data(self.acc_raw, self.gyro_raw, self.mag_raw, self.time_raw,True,self.calibration_callback)
            self.imu.update_mag_offset()
            
            # finish calibrating
            if self.imu.calibarated:
                print("Calibration finished")
                self.time_start = time.time()
                self.state = STATE_READ_DATA
                self.finish_calibration_callback(self)

        elif self.state == STATE_READ_DATA:
            # read data
            self.imu.set_data(self.acc_raw, self.gyro_raw, self.mag_raw, self.time_raw, True, self.receive_callback)
            if self.write_csv and self.writing_csv:
                self.imu.write_csv(self.csv)