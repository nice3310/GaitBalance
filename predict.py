import os
import re
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import scipy.stats as stats
import tflite_runtime.interpreter as tflite
from datetime import datetime

import warnings
from sklearn.exceptions import DataConversionWarning

# 忽略 DataConversionWarning 警告
warnings.filterwarnings("ignore", category=DataConversionWarning)

class Predict(): 

    def __init__(self):
        self.interpreter = tflite.Interpreter(model_path='/home/pi/GaitBalanceSystem/model/tflite_runtime_model.tflite')
        self.interpreter.allocate_tensors()
        self.input_index = self.interpreter.get_input_details()[0]['index']
        self.output_index = self.interpreter.get_output_details()[0]['index']
    
    def cal(self, data, file):
        X = []
        Y = []
        filename = []

        row, column = data.shape
        data_col_name = data.columns


        # # 刪除磁力計資料_TUG_V0805
        # data = data.drop(data.columns[58:], axis=1)
        # data = data.drop(data.columns[4:49], axis=1)
        data = data.drop(data.columns[:6], axis=1)
        data = data.drop(data.columns[9:], axis=1)

        row, colume = data.shape
        data_col_name = data.columns

        task_ID = file
        number = 1
        task_StartEnd = pd.DataFrame(columns=["task", "start", "end"])
        f = 0
        i = 0
        while i<row: 
            task_StartEnd.loc[number , "start"] = 1          
            if i == row:
                task_StartEnd.loc[number , "end"] = i-1
                number += 1
            # task_ID = chr(ord(task_ID) + 1)
                i-=1
            i+=1
        task_StartEnd.loc[number , "end"] = i-1        
        
        # 設定 window size、前後筆資料重複率
        window_size = 150       # sample rate = 50Hz，取一秒的資料
        Repeat_ratio = int(window_size * (100 / 100))      # 重複比率0%

        BBS_average = 0
        # 切割訓練資料
        task_ID = 'T'
        for i in range(0, 1):
            start = task_StartEnd.at[i+1, 'start'] + 50
            end = task_StartEnd.at[i+1, 'end'] + 1 - 50
            total = end - start
            print(total)
            training_set = data.iloc[start:end, :colume].values
            training_set = stats.zscore(training_set)
            sample_count = 0
            BBS_total = 0
            BBS_results = []  # 用于存储每3次预测的结果
            for j in range(0, total, Repeat_ratio):
                if j + window_size <= total:
                    sample = training_set[j:j + window_size]  # (150, 9)
                    sample = np.reshape(sample, (1, 150, 9))  # 将样本重塑为 (1, 150, 9)
                    sample_count += 1                
                    input_data = sample.astype(np.float32)
                    self.interpreter.set_tensor(self.input_index, input_data)
                    self.interpreter.invoke()

                    BBS = [[0], [56]]
                    BBS_array = np.array(BBS)
                    BBS_scaler = MinMaxScaler(feature_range=(0, 1)).fit(BBS_array)
                    # 获取输出
                    BBS_pred = self.interpreter.get_tensor(self.output_index)
                    BBS_pred = BBS_scaler.inverse_transform(BBS_pred)
                    BBS_pred = np.around(BBS_pred)
                    BBS_pred = np.mean(BBS_pred)
                    print(BBS_pred)              
                    BBS_total = BBS_total + BBS_pred      
            BBS_average = BBS_total / sample_count
            print("BBS score : " , BBS_average)

        return BBS_average

    def predict_process(self):
        # # 定义 dirs 变量
        # path = '/home/pi/GaitBalanceSystem/GaitData/'
        # dirs = os.listdir(path)
        
        # # 为每个输入文件进行预测，并将结果保存到单独的文件中
        # for files in dirs:
        #     DatasetPath = path + files
        #     data_or = pd.read_csv(DatasetPath)
        #     print(files)
            
        #     # 计算 BBS_average
        #     BBS_average = self.cal(data_or, files[-5])
            
        #     # 将 BBS_average 存储到一个新文件中
        #     result = {'Filename': files, 'BBS_average': BBS_average}
        #     result_df = pd.DataFrame(result, index=[0])
        #     result_df['BBS_average'] = result_df['BBS_average'].apply(lambda x: re.sub(r'\[|\]', '', str(x)))
        #     result_df.to_csv('GaitData/BBS_averages_' + files + '.csv', mode='w', index=False)
        # 定义 dirs 变量
        path = '/home/pi/GaitBalanceSystem/GaitData/'
        dirs = os.listdir(path)
        
        # 为每个输入文件进行预测，并将结果保存到单独的文件中
        for filename in dirs:
            DatasetPath = os.path.join(path, filename)
            data_or = pd.read_csv(DatasetPath)
            print(filename)
        
            # 如果数据量小于250，则不进行预测
            if len(data_or) < 250:
                print("Not enough data")
                continue
            
            # 解析日期
            date_str = filename.split('_')[-2]  # 提取日期部分
            datetime_obj = datetime.strptime(date_str, '%Y-%m-%d')  # 解析为 datetime 对象
            formatted_date = datetime_obj.strftime('%Y/%m/%d')  # 格式化为所需的字符串形式
            
            # 计算 BBS_average
            BBS_average = self.cal(data_or, filename[-5])
            
            # 将 BBS_average 存储到一个新文件中
            result = {'Date': formatted_date, 'BBS_average': BBS_average}
            result_df = pd.DataFrame(result, index=[0])
            result_df['BBS_average'] = result_df['BBS_average'].apply(lambda x: re.sub(r'\[|\]', '', str(x)))
            result_df.to_csv('GaitData/BBS_averages_' + filename + '.csv', mode='w', index=False)

