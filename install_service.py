import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import subprocess

class YeiMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "YeiMonitorService"
    _svc_display_name_ = "YEI Monitor Service"
    _svc_description_ = "YEI协议监控服务"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.process:
            self.process.terminate()

    def SvcDoRun(self):
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PID_INFO,
                ('Starting %s' % self._svc_name)
            )
            
            # 获取脚本所在目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            yei_dir = os.path.join(script_dir, "yei_monitor")
            os.chdir(yei_dir)
            
            # 启动主程序
            self.process = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=yei_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # 等待进程结束
            self.process.wait()
            
        except Exception as e:
            servicemanager.LogErrorMsg(str(e))
            raise

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(YeiMonitorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(YeiMonitorService) 