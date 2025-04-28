from multiprocessing import Queue
import time

PACKET_SIZE = 36
MAG_CALI_TIMES = 2000
WRITE_PC_TIMESTAMP = True

class Time():
    _hour = 0
    _minute =0
    _second = 0
    _millisecond = 0
    total_time = 0

    def set_time(self, hour, minute, second, ms_h, ms_l):
        self._hour = hour
        self._minute = minute
        self._second = second
        self._millisecond = ms_h << 8 | ms_l
        self.total_time = self._hour*60*60*1000 + self._minute*60*1000 + self._second*1000 + self._millisecond

class IMU():
    # data
    id = 0

    # offset
    acc_total = [0,0,0]
    gyro_total = [0,0,0]
    mag_total = [0,0,0]  
    acc_offset = [0,0,0]
    gyro_offest = [0,0,0]
    mag_offset = [0,0,0]
    mag_scale = [1,1,1]
    mag_max = [-32767, -32767, -32767]
    mag_min = [32767, 32767, 32767]
    the_mag = [0,0,0]
    mag_total = [0,0,0]
    calibarated = False
    mag_cali_times = MAG_CALI_TIMES
    processed = 0


    past_time = 0
    delt = 0

    acc = [0,0,0]
    gyro = [0,0,0]
    mag = [0,0,0]
    _time = Time()

    # scale
    gres = 2000 / 32768 # 2000 dps
    ares = 16 / 32768 # 16g
    mres = 10 * 4912 / 32760 # 16 bit, mGauss
    

    def __init__(self, use_offset=True, save_offset=True, load_mag_offset=False, offset_file="", mag_cali_times=MAG_CALI_TIMES):
        if load_mag_offset:
            self.calibarated = True
            self.load_offset(offset_file)

        if not use_offset:
            self.calibarated = True
            print(f"Skip Calibration")

        self.use_offset = use_offset
        self.save_offset = save_offset
        self.mag_cali_times = mag_cali_times
        self.offset_file = offset_file

    #------------------------------
    # set IMU Data
    def set_data(self, acc, gyro, mag, time , use_calllback=False, callback=lambda acc,gyro,mag,proc,time,delt,cali_times:None):
        self.processed += 1
        self.calc_acc(acc)
        self.calc_gyro(gyro)
        self.calc_mag(mag)
        self._time.set_time(time[0],time[1],time[2],time[3],time[4])
        self.calc_delt()

        if use_calllback:
            callback(self.acc,self.gyro,self.mag,self.processed,self._time,self.delt,self.mag_cali_times)

     #------------------------------
    # calculations
    def calc_delt(self):
        current_time = self._time.total_time
        self.delt = current_time - self.past_time
        self.past_time = current_time

    def calc_acc(self,acc):
        for i in range(3):
            twos =  acc[2*i] << 8 | acc[2*i+1] & 0xff
            self.acc[i] = self.twos_comp(twos) * self.ares
    
    def calc_gyro(self,gyro):
        for i in range(3):
            twos = gyro[2*i] << 8 | gyro[2*i+1] & 0xff
            self.gyro[i] = self.twos_comp(twos)  * self.gres

    def calc_mag(self,mag):
        for i in range(3):
            twos = mag[2*i] << 8 | mag[2*i+1] & 0xff
            self.the_mag[i] = self.twos_comp(twos)
            if self.calibarated:
                self.mag[i] = (self.the_mag[i] * self.mres - self.mag_offset[i]) * self.mag_scale[i]
            else:
                self.mag[i] = self.the_mag[i] * self.mres

    def twos_comp(self,val):
        if (val & (1 << (16 - 1))) != 0: 
            val = val - (1 << 16)
        return val

    def update_mag_offset(self):        
        for i in range(3):
            # self.mag_total[i] += self.the_mag[i] * self.mres
            self.mag_max[i] = max( self.mag_max[i], self.the_mag[i])
            self.mag_min[i] = min( self.mag_min[i] , self.the_mag[i])
            # if self.the_mag[i] > self.mag_max[i]:
            #     self.mag_max[i] = self.the_mag[i]
            # if self.the_mag[i] < self.mag_min[i]:
            #     self.mag_min[i] = self.the_mag[i]



        if self.processed >= self.mag_cali_times:
            # hard iron correction
            self.mag_offset[0] = (self.mag_max[0] + self.mag_min[0]) /2
            self.mag_offset[1] = (self.mag_max[1] + self.mag_min[1]) /2
            self.mag_offset[2] = (self.mag_max[2] + self.mag_min[2]) /2
            # self.mag_offset[0] = self.mag_total[0] / self.mag_cali_times
            # self.mag_offset[1] = self.mag_total[1] / self.mag_cali_times
            # self.mag_offset[2] = self.mag_total[2] / self.mag_cali_times

            # soft iron correction estimate
            self.mag_scale[0] = (self.mag_max[0] - self.mag_min[0]) /2
            self.mag_scale[1] = (self.mag_max[1] - self.mag_min[1]) /2
            self.mag_scale[2] = (self.mag_max[2] - self.mag_min[2]) /2
            avg_rad = sum(self.mag_scale)/3
            for i in range(3):
                self.mag_scale[i] = avg_rad / self.mag_scale[i]

            self.calibarated = True
            self.processed = 0
            self.save_offset_csv()
            print(f"Max: {self.mag_max[0]} / {self.mag_max[1]} / {self.mag_max[2]}")
            print(f"Min: {self.mag_min[0]} / {self.mag_min[1]} / {self.mag_max[2]}")
            print(f"Offset: {self.mag_offset[0]} / {self.mag_offset[1]} / {self.mag_offset[2]} ")
            print(f"Scale: {self.mag_scale[0]} / {self.mag_scale[1]} / {self.mag_scale[2]}")

    def load_offset(self, path):
        with open(path,"r") as f:
            offset_str = f.read()
            offset_list = offset_str.split(",")
            self.mag_offset[0] = float(offset_list[0])
            self.mag_offset[1] = float(offset_list[1])
            self.mag_offset[2] = float(offset_list[2])   

            if len(offset_list) >= 6:
                self.mag_scale[0] = float(offset_list[3])
                self.mag_scale[1] = float(offset_list[4])
                self.mag_scale[2] = float(offset_list[5])

            print(f"Loaded Offset: {self.mag_offset[0]} / {self.mag_offset[1]} / {self.mag_offset[2]} / {self.mag_scale[0]} / {self.mag_scale[1]} / {self.mag_scale[2]}")

    def save_offset_csv(self):
        if self.save_offset:
            with open(self.offset_file,"w") as f:
                offset_data = self.mag_offset
                offset_data.extend(self.mag_scale)
                csv_str = ",".join([str(n) for n in offset_data])
                f.write(csv_str)        

    def write_csv(self, file):
        try:
            if WRITE_PC_TIMESTAMP:
                file.write(f"{self.processed},{self._time._hour},{self._time._minute},{self._time._second},{self._time._millisecond},{self.delt},{self.acc[0]},{self.acc[1]},{self.acc[2]},{self.gyro[0]},{self.gyro[1]},{self.gyro[2]},{self.mag[0]},{self.mag[1]},{self.mag[2]},{time.time()}\n")
            else:
                file.write(f"{self.processed},{self._time._hour},{self._time._minute},{self._time._second},{self._time._millisecond},{self.delt},{self.acc[0]},{self.acc[1]},{self.acc[2]},{self.gyro[0]},{self.gyro[1]},{self.gyro[2]},{self.mag[0]},{self.mag[1]},{self.mag[2]}\n")
        except:
            pass