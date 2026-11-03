import pyautogui
import time
time.sleep(5)
b = "busca trabajo"
i=1
for i in range(5):
    pyautogui.write(str(i) + b)
    pyautogui.press('enter')
    time.sleep(0.1)