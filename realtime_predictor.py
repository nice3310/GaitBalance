#!/usr/bin/env python3
# realtime_predictor_led.py
#
# 連 IMU → 推論 BBS → LED 狀態指示
#   - bbs.txt 　：最新數值（向下相容先前做法）
#   - bbs.json ：最近 HISTORY_LEN 筆環形緩衝，前端一次就能畫歷史折線
#
# ────────────────────────────────────────────────────────────
import argparse, collections, datetime, json, os, tempfile
from pathlib import Path
from signal import pause

import numpy as np
import scipy.stats as stats
import tflite_runtime.interpreter as tflite
from gpiozero import LED, Button
from sklearn.preprocessing import MinMaxScaler
from receiver.receiver import IMU_Receiver

# ── 檔案 / 硬體 / 模型設定 ─────────────────────────────────────
LED_PIN, BTN_PIN     = 12, 18
MAC_ADDR, RFCOMM_PORT = '00:1A:FF:06:5A:17', 1
MODEL_PATH            = '/home/pi/GaitBalanceSystem/model/tflite_runtime_model.tflite'

WEB_DIR      = Path('bbs_web')
WEB_DIR.mkdir(exist_ok=True)
TXT_PATH     = WEB_DIR / 'bbs.txt'
JSON_PATH    = WEB_DIR / 'bbs.json'
HISTORY_LEN  = 360       # 最近 360 秒（@1 Hz ≈ 6 分鐘）

# ── Predictor ───────────────────────────────────────────────
class Predictor:
    WINDOW = 150
    def __init__(self):
        self.inter = tflite.Interpreter(model_path=MODEL_PATH)
        self.inter.allocate_tensors()
        self.in_idx  = self.inter.get_input_details()[0]['index']
        self.out_idx = self.inter.get_output_details()[0]['index']
        self.scaler  = MinMaxScaler((0, 1)).fit([[0], [56]])

    def infer(self, win: np.ndarray) -> int:
        z = stats.zscore(win).reshape((1, 150, 9)).astype('float32')
        self.inter.set_tensor(self.in_idx, z)
        self.inter.invoke()
        y = self.inter.get_tensor(self.out_idx)
        return round(float(self.scaler.inverse_transform(y)[0, 0]))

# ── Pipeline ────────────────────────────────────────────────
class Pipeline:
    def __init__(self, led: LED, overlap: float):
        self.led     = led
        self.pred    = Predictor()
        self.buf     = collections.deque()
        self.step    = int(self.pred.WINDOW * (1 - overlap))
        self.active  = False
        self.hist    = collections.deque(maxlen=HISTORY_LEN)

        self.rec = IMU_Receiver(
            connection_type='MAC',
            mac_address=MAC_ADDR,
            rfcomm_port=RFCOMM_PORT,
            load_offset=True, save_offset=False,
            packet_size=36,
            receive_callback=self._on_sample
        )

    # 連線＋LED 指示
    def start(self):
        self.led.blink(0.2, 0.2)               # → 連線嘗試中
        if self.rec.com_connect():
            self.active = True
            self.led.on()                      # → 連線成功
            print('✅  IMU connected — realtime ON')
        else:
            self.led.off()                     # → 連線失敗
            print('❌  IMU connect failed')

    def stop(self):
        self.active = False
        self.rec.com_disconnect()
        self.led.off()                         # → 中斷/停止
        print('⏹️  pipeline stopped')

    # 收資料 → 推論 → 寫檔
    def _on_sample(self, acc, gyro, mag, processed, *_):
        if not (self.active and processed):
            return

        # 累積 raw 資料
        self.buf.append(acc + gyro + mag)
        if len(self.buf) < self.pred.WINDOW:
            return

        win = np.asarray(list(self.buf)[-self.pred.WINDOW:], dtype=np.float32)
        bbs = self.pred.infer(win)

        # ──(1) 寫最新值 txt（單行覆寫）──────────────────────
        TXT_PATH.write_text(f'{bbs}\n')

        # ──(2) 更新 json ring-buffer ───────────────────────
        now_iso = datetime.datetime.now().isoformat(timespec='seconds')
        self.hist.append({'t': now_iso, 'bbs': bbs})

        with tempfile.NamedTemporaryFile('w', dir=str(WEB_DIR),
                                         delete=False, suffix='.tmp') as tmp:
            json.dump(list(self.hist), tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
            Path(tmp.name).rename(JSON_PATH)

        # ──(3) 控制緩衝區滑窗 ─────────────────────────────
        for _ in range(self.step):
            if self.buf:
                self.buf.popleft()

        # Debug log
        print(f'[{now_iso[11:]}] BBS = {bbs}')

# ── GPIO & main ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Realtime BBS predictor (LED status)')
    parser.add_argument('--overlap', type=float, default=0.0,
                        help='Overlap ratio 0–1 (0=3 s/次, 0.5=1.5 s/次)')
    args = parser.parse_args()
    if not (0.0 <= args.overlap < 1.0):
        parser.error('overlap 必須在 0~1 之間')

    led, btn = LED(LED_PIN), Button(BTN_PIN, hold_time=3)
    pipe     = Pipeline(led, overlap=args.overlap)
    running  = {'on': False}

    def start():
        if running['on']:
            return
        pipe.start()
        running['on'] = pipe.active      # 只有成功才算開始

    def stop():
        if not running['on']:
            return
        pipe.stop()
        running['on'] = False

    btn.when_held     = start            # 長按 3 s 開始
    btn.when_released = stop             # 放開停止
    led.blink(0.5, 0.5, n=3, background=True)  # 開機提示
    pause()

if __name__ == '__main__':
    main()
