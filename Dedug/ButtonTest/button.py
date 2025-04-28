from gpiozero import Button, LED
import time
# 
led = LED(12)


#19 13 6 5 0 11 26
# button = Button(19)
# button = Button(14)
button1 = Button(15)
button2 = Button(18)
# button2 = Button(24)
# button3 = Button(25)
# button4 = Button(1)
# button5 = Button(16)
# button6 = Button(21)


while True:
#     if button.is_pressed:
#         print(14)
#         led.on()
# 
#         time.sleep(0.1)
#     led.off()

    if button1.is_pressed:
        print(15)
        led.on()

        time.sleep(0.1)
    led.off()

    if button2.is_pressed:
        print(18)
        led.on()
        time.sleep(0.1)

    led.off()

#     if button3.is_pressed:
#         print(1)
#         led.on()
#         ledG.on()
#         time.sleep(0.1)
#     led.off()
#     ledG.off()
#     if button4.is_pressed:
#         print(1)
#         led.on()
#         ledG.on()
#         time.sleep(0.1)
#     led.off()
#     ledG.off()
#     if button5.is_pressed:
#         print(1)
#         led.on()
#         ledG.on()
#         time.sleep(0.1)
#     led.off()
#     ledG.off()
#     if button6.is_pressed:
#         print(21)
#         led.on()
#         ledG.on()
#         time.sleep(0.1)
#     led.off()
#     ledG.off()

