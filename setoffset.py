from receiver.receiver import IMU_Receiver

mac_address = "00:1A:FF:06:5A:39" #IMU mac address
rfcomm_port = 1

def finish_calibration_callback(receiver):
    print("finish calibration")
    receiver.com_disconnect()
    print("Disconnected")
    receiver.close_queue()
    print("Queue closed")


receiver = IMU_Receiver(connection_type="MAC", mac_address=mac_address, rfcomm_port=rfcomm_port, load_offset=False, save_offset=True, use_offset = True,  packet_size=36, finish_calibration_callback=finish_calibration_callback)
if receiver.com_connect():
    print("Connected and started calibration")