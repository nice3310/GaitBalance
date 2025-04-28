import os
import shutil

class FileBackup:

    def backup_files(self):
        source_path = "/home/pi/GaitBalanceSystem/GaitData/"
        destination_path = "/home/pi/GaitBalanceSystem/Backup/"
        
        # 复制所有文件
        for file_name in os.listdir(source_path):
            if file_name.endswith('.csv'):
                source_file_path = os.path.join(source_path, file_name)
                destination_file_path = os.path.join(destination_path, file_name)
                shutil.copyfile(source_file_path, destination_file_path)
                os.remove(source_file_path)
        
        print("Files backed up successfully.")