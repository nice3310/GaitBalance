from predict import Predict
from backup import FileBackup

def main():
    predict_process = Predict()
    predict_process.predict_process()
    back_up = FileBackup()
    FileBackup().backup_files()


if __name__ == "__main__":
    main()