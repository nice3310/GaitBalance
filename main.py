# LED GPIO 12
# Button1 GPIO 14
# Button2 GPIO 15
# Button3 GPIO 18

from gpiozero import LED
led = LED(12)
led.on() #等待import時間指示燈亮啟

import sys
import time
import threading
import datetime
import csv
import os
from receiver.receiver import IMU_Receiver
from gpiozero import Button

walk_start_stop_button = Button(18)

mac_address = "00:1A:FF:06:5A:2A" #IMU mac address
rfcomm_port = 1

button_lock_duration_walk = 5
last_button_press_time_walk = 0
time.sleep(1)
led.off()
time.sleep(1)
led.on()
time.sleep(1)
led.off()
time.sleep(1)
led.on()
time.sleep(1)
led.off()

def main():
    global data_collection_active
    global last_button_press_time_walk
    
    data_collection_active = False
    last_button_press_time_walk = 0

    while True:
        last_button_press_time_walk = handle_button_press(walk_start_stop_button, last_button_press_time_walk, button_lock_duration_walk, 'Walk')

def handle_button_press(button, last_button_press_time, button_lock_duration, data_collection_key):
    global data_collection_active
    current_time = time.time()
    if button.is_pressed and (current_time - last_button_press_time >= button_lock_duration):
        led.on()
        time.sleep(1)
        led.off()
        last_button_press_time = current_time
        if not data_collection_active:
            start_data_collection(data_collection_key)
            data_collection_active = True
        else:
            stop_data_collection()
            data_collection_active = False
    return last_button_press_time

def start_data_collection(task):
    global receiver
    receiver = IMU_Receiver(connection_type="MAC", mac_address=mac_address, rfcomm_port=rfcomm_port, load_offset=True, save_offset=False,  packet_size=36)
    if receiver.com_connect():
        id = read_id_from_csv()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        csv_path = f"/home/pi/GaitBalanceSystem/GaitData/{id}_{task}_{timestamp}.csv"
        receiver.create_csv(True, csv_path)
        led.on()
        receiver.start_write_csv()
        print("Connected and started receiving data")

def stop_data_collection():
    global receiver
    if hasattr(receiver, 'com_disconnect'):
        receiver.com_disconnect()
        print("Disconnected")
        receiver.close_queue()
        print("Queue closed")
        led.off()

def read_id_from_csv():
    # 讀取ID.csv中的ID
    id = "default"
    try:
        with open('ID.csv', 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                id = row[0]
    except Exception as e:
        print("Error reading ID from CSV:", e)
    return id

if __name__ == "__main__":
    main()
