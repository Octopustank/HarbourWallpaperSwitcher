#!/usr/bin/python3
import os
import cnlunar as cl
import datetime as dt
import json as js
from astral import LocationInfo, sun
import time as tm
import subprocess as sb


SEASON_DIC = {"春":"spring", "夏":"summer", "秋":"autumn", "冬":"winter"}
TIME_DIC = ["night", "dawn", "noon", "dusk", "night"]
PATH = JSON_PATH = LOG_PATH = os.getcwd()
PIC_PATH = os.path.join(PATH, "portview") # 港区图片路径
LOG_FILE = os.path.join(LOG_PATH, "wallpaper.log") # 日志文件路径
DATA_FILE = os.path.join(JSON_PATH, "data.json") # 数据文件路径
TEMP_FILE = os.path.join(JSON_PATH, "temp.json") # 临时文件路径
CHECK_INTERVAL = 300  # 检查间隔(秒)，每5分钟检查一次

with open(DATA_FILE, "r") as f:
    data = js.load(f)
    location = data["location"]
    LONGITUDE = location["longitude"]
    LATITUDE = location["latitude"]

def log(_class, words, data = None, init=False):
    time = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prt = f"{time}: [{_class}] {words}\n"
    if data is not None:
        prt = prt + f"  {data}\n"
    with open(LOG_FILE, "w" if init else "a") as f:
        f.write(prt)
        

class Engine:
    def __init__(self):
        self.__dialog("init","开始初始化")

        self.season_dic = SEASON_DIC #季节中英文对应
        self.time_dic = TIME_DIC #一天中的时间段
        self.pic_path = PIC_PATH #图片路径
        self.json_path = JSON_PATH #数据存储位置
        self.gps_wait = 5 #GPS请求等待时长


        self.get_time() #初始化当前时间self.now、self.today_ISO
        self.location = {"longitude": LONGITUDE, "latitude": LATITUDE} #初始化地点 格式:[经度、纬度]
        self.season = None #初始化季节
        self.today_periods = None #初始化当日时间节点
        self.period_now = -1 #初始化当前处于的时间段序号

        self.__get_time_zone()#获取当前时区(datetime.deltatime)

        self.__check_datafile() #检查数据文件

        rd = self.__read_data()
        self.update_time = rd["time"] #读取/初始化慢更新数据的更新时间 格式:[year,week,weekday]
        self.__dialog("read","读档读得",rd)

        self.__dialog("init","初始化完成","\n")


    def get_time(self): #获取当天时间数据
        self.now = dt.datetime.now() #时间
        self.today_ISO = list(dt.date.isocalendar(self.now)) #ISO[year,week,weekday]格式日期


    def __get_time_zone(self): #获取当前时区
        delt_utc = dt.datetime.now()-dt.datetime.utcnow()
        self.time_zone = dt.timezone(delt_utc)
        self.__dialog("timezone","时区:",self.time_zone)


    def __check_datafile(self): #检查数据文件(若不存在，则创建)
        if not os.path.exists(TEMP_FILE):
            self.__save_data(None, True)

    def __save_data(self, data, creat = False): #保存数据文件
        if not creat: #不初始化数据文件,正常读取字典
            with open(TEMP_FILE,"r") as f:
                dic = js.load(f)
        else: #初始化数据文件所用字典
            dic = {}

        dic["location"] = data
        dic["time"] = self.today_ISO

        with open(TEMP_FILE,"w") as f:
            js.dump(dic,f) #写入文件


    def __read_data(self): #读取数据文件,返回字典
        with open(TEMP_FILE,"r") as f:
            dic = js.load(f)
        return dic


    def __dialog(self, _class, words, data = None): #交互
        prt = f"[{_class}] {words}"
        if data is not None:
            prt = prt + f"\n  {data}"
        print(prt)
        log(_class, words, data)


    def get_season(self): #计算季节

        today_lunar = cl.Lunar(self.now, godType='8char') #创建农历日期对象
        today_season = today_lunar.lunarSeason #获取季节
        self.season = self.season_dic[today_season[-1]] #转为所需格式
        self.__dialog("season","季节:",self.season)


    def get_periods(self): #获取当天时间节点
##        self.__dialog("time_period","计算时间段")
        location_dic = self.location

        location = LocationInfo('User', 'China', self.time_zone, location_dic["latitude"], location_dic["longitude"]) #创建地点对象
        s = sun.sun(location.observer, date = self.now, tzinfo = self.time_zone) #计算太阳时段

        tz_off = lambda x:x.replace(tzinfo = None)
        self.today_periods = list(map(tz_off, [s["dawn"], s["sunrise"], s["sunset"], s["dusk"]])) #获取所需数据并去除时区

        self.__dialog("time_period","时间节点:","\n  ".join(list(map(str,self.today_periods))))


    def cal_period(self): #定位时间段
##        self.__dialog("time_period","定位时间段")
        periods = self.today_periods
        nw = self.now

        nw_period = 0
        while  nw_period < len(periods) and nw > periods[nw_period]: #定位
            nw_period += 1

        self.__dialog("time_period","现在处于:", self.time_dic[nw_period])

        if nw_period != self.period_now: #若有变化
            self.period_now = nw_period #更新时间段定位
            return True
        else:
            return False


    def update(self): #调用全部获取(慢更新)
        self.update_time = self.today_ISO #跟进更新时间


    def change_screen(self): #调用完成更改锁屏壁纸
        pic_path = self.pic_path
        season = self.season
        period_now = self.time_dic[self.period_now]

        dir_list = os.listdir(pic_path)
        file = None
        for i in dir_list: #寻找所需壁纸文件
            if season in i:
                if period_now in i:
                    file = i
                    break
        if file is None:
            self.__dialog("change_bg", f"找不到符合季节为{season}，天色为{period_now}的壁纸")
            exit(1)
        file_path = os.path.join(pic_path, file)
        self.__dialog("change_bg","修改锁屏壁纸",file_path)
        command = f'gsettings set org.gnome.desktop.background picture-uri "file://{file_path}"'
        res = os.system(command) #调用命令

        self.__dialog("change_bg",res)


    def cal_delta_time(self): #计算距下一时间点的时长(s)
        today = self.now

        dt_max = dt.datetime.max
        today_end = today.replace(hour=dt_max.hour,minute=dt_max.minute,second=dt_max.second,microsecond=dt_max.microsecond)
        time_periods = self.today_periods + [today_end] #增加23:59:59:...的末节点

        next_period_start = time_periods[self.period_now] #计算时长
        delta_time = next_period_start - dt.datetime.now()
        next_time = delta_time.seconds
        self.__dialog("delta_time","下一时间节点(s):",next_time)
        return next_time


    def run(self): #运行时调用(快更新)
        self.__dialog("main","运行",dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.get_time() #刷新程序时间

        if self.today_ISO != self.update_time:
            #若信息过期
            self.get_season()
            self.get_periods()
            self.update()
        elif self.season is None or self.today_periods is None:
            #若季节或时间段缺失
            self.get_season()
            self.get_periods()

        res = False
        res = self.cal_period()
        if res: #若时间段发生变化
            self.change_screen() #调用更改壁纸

        next_time = self.cal_delta_time() #获取下一次等待时长
        self.__dialog("main","完成一次运行",f"更改:{res}\n")
        return next_time + 1


if __name__ == "__main__":
    log("init", "start up", init=True)
    
    engine = Engine()
    while True:
        engine.run()
        tm.sleep(CHECK_INTERVAL)
