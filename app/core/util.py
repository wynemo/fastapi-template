import datetime

def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def unix_time_now():
    return int(datetime.datetime.now().timestamp())

def run_cmd(cmd):
    import subprocess
    return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()