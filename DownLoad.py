import requests
import threading
import time
import hashlib
import os


class Down:
    """简易下载器 Demo """

    def __init__(self):
        self.__url = None
        self.__verify = True
        self.__size = None
        self.__name = None
        self.__back_name = None
        self.__thread = 1
        self.__data_count = 0
        self.__flag = False
        self.__extend_name = None
        self.__file_type = None
        self.__isMd5 = True
        self.__MD5 = None
        self.__cookie = None
        self.__lock = threading.Lock()
        # 是否支持多线程下载
        self.__is_thread = True
        self.__response_headers = None
        self.__type = ['html', 'png', 'jpeg']
        self.plugin = []
        self.__headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/63.0.3239.84 Safari/537.36',
        }

    def set_cookie(self, cookie: str):
        self.__cookie = cookie

    def set_url(self, url):
        self.__url = url

    def set_filename(self, name: str):
        self.__name = name

    def set_isMd5(self, md5: bool):
        self.__isMd5 = md5

    def get_flag(self):
        return self.__flag

    def _get_response_headers(self):
        """获取服务器响应信息"""
        print("玩命获取数据中....\n")
        response = requests.head(self.__url, headers=self.__headers, verify=self.__verify)
        if str(response.status_code)[0] == '4' or str(response.status_code)[0] == '5':
            raise Exception("下载失败 错误码 {},请检查是否有访问权限,或者尝试带上cookie".format(response.status_code))
        """请求为302是 则迭代找寻源文件"""
        while response.status_code == 302:
            if 'Location' in response.headers:
                self.__url = response.headers['Location']
            else:
                raise Exception("获取原始地址失败！")
            response = requests.head(self.__url, headers=self.__headers, verify=self.__verify)
            if 'Content-Length' in response.headers:
                self.__response_headers = response
                return
            else:
                continue
        """不等于302 直接赋值"""
        if 'Content-Length' in response.headers:
            self.__response_headers = response
            return
        else:
            raise Exception(" 获取文件信息失败")

    def _get_file_size(self):
        """获取文件大小"""
        self.__size = self.__response_headers.headers['Content-Length']

    def _chuck_thread(self):
        """验证是否支持多线程"""
        if 'Accept-Ranges' not in self.__response_headers.headers:
            self.__is_thread = False

    def _get_file_type(self):
        """获取文件类型"""
        if 'content-type' in self.__response_headers.headers:
            content_type = self.__response_headers.headers['content-type']
            for i in self.__type:
                if i in content_type and self.__response_headers.status_code == 200:
                    self.__file_type = i
                    if self.__name is None:
                        self.__name = 'index'
                        # 判断一下要不然扩展名就重了
                        if '.' not in self.__name:
                            self.__extend_name = i

    def _get_file_name(self):
        name_list = ['<', '>', '/', '\\', '|', ':', '"', '*', '?']
        """获取文件名"""
        if '/' in self.__url:
            self.__name = self.__url.split('/')[-1][:255]
            """防止windows命名错误"""
            for i in name_list:
                if i in self.__name:
                    self.__name = self.__name.replace(i, '')
            return
        """尝试在响应头获取文件名"""
        if 'Content-Disposition' in self.__response_headers.headers:
            self.__back_name = self.__response_headers.headers['Content-Disposition'].split("filename=")[-1]
            if '"' in self.__back_name:
                self.__back_name = eval(self.__back_name)
            if self.__name is None:
                self.__name = self.__back_name

    def _text_download(self):
        """文本文件下载函数,一般用不到"""
        html = requests.get(self.__url, headers=self.__headers, stream=True, verify=self.__verify)
        if html.status_code != '200' or html.status_code != '206':
            raise Exception("下载失败状态码 {}".format(html.status_code))
        with open(self.__name, "wb") as file:
            file.write(html.content)

    def _down_load(self, start, end):
        """分段下载函数"""
        headers = self.__headers.copy()
        # 支持多线程就更新请求头
        if self.__is_thread:
            headers.update({'Range': 'bytes={}-{}'.format(start, end)})
        response = requests.get(self.__url, headers=headers, verify=self.__verify, stream=True)
        # 重试
        while str(response.status_code)[0] == '4' or str(response.status_code)[0] == '5':
            response = requests.get(self.__url, headers=headers, verify=self.__verify, stream=True)
            time.sleep(2)
        with open(self.__name, "rb+") as file:
            # 再写入文件直接调整指针，多线程下载可避免文件错乱
            file.seek(start)
            # 分次写入文件，可以防止文件过大时全部下载到内存再写入文件
            for i in response.iter_content(chunk_size=2048):
                file.write(i)
                """不上锁进度条好像小概率乱"""
                self.__lock.acquire()
                self.__data_count += len(i)
                self.__lock.release()
        return

    def _create_file(self):
        """创建相同大小文件,获取文件大小之后调用"""
        with open(self.__name, "wb") as file:
            try:
                file.truncate(int(self.__size))
            except OSError:
                print("磁盘已满,至少需要 {} MB空间".format(self.__size / 2 ** 20))
                return

    def _start_thread(self):
        """计算每个线程需要下载多少数据"""
        part = int(int(self.__size) / int(self.__thread))
        thread_list = []
        for i in range(self.__thread):
            start = int(i * part)
            end = int((i + 1) * part - 1)
            if i == self.__thread - 1:
                end = int(self.__size)
            thread_list.append(threading.Thread(target=self._down_load, args=(start, end,)))
            """进度条线程"""
        threading.Thread(target=self._draw_able).start()
        for i in thread_list:
            i.start()
        for i in thread_list:
            i.join()

    def _chuck_md5(self):
        """MD5检验"""
        md5_value = hashlib.md5()
        with open(self.__name, 'rb') as f:
            while True:
                data = f.read(2048)
                if not data:
                    break
            md5_value.update(data)
        if self.__MD5 is not None:
            if md5_value.hexdigest() != self.__MD5:
                print('\r当前文件MD5不一致，请检查文件是否被篡改')

        else:
            print('\rMD5值: ' + md5_value.hexdigest())

    def _welcome(self):
        print("MD5校验:{} ".format(self.__isMd5))
        print("文件名:{} ".format(self.__name))
        print("文件名大小:{} MB".format(int(int(self.__size) / 2 ** 20)))
        print("是否支持多线程: {}".format(self.__is_thread))
        print("线程数:{}".format(self.__thread))
        print("文件下载地址: {}".format(self.__url))
        print("是否有cookie: {} ".format(bool(self.__cookie)))
        print()

    # 进度条
    def _draw_able(self):
        """s = v/t 路程 = 速度 / 时间  下载速度计算应计算一个时间段内的速度"""
        while not self.__flag:
            # 上一个时间段下载的数据
            start_time = int(time.time())
            data_tmp = self.__data_count
            time.sleep(1)
            try:
                schedule = (int(self.__data_count) / int(self.__size) * 100)
            except ZeroDivisionError:
                schedule = 0
            # 用当前时间段下载的数据减去上一个时间段下载的数据就是这一段时间内下载的数据
            speed = (int(self.__data_count - data_tmp) / (int(time.time()) - start_time) / 2 ** 20)
            unit = ' MB/s'
            if speed < 1:
                speed = speed * 2 ** 10
                unit = 'kb/s'
            print("\r文件下载进度 - > {}{:.2f}% ".format('>' * int(schedule), schedule) + " {:.2f}".format(speed) + unit,
                  end=" ")

    def __chuck(self):
        """检查运行必须的参数"""
        if self.__url is None:
            raise Exception('未设置下载链接')
        """更新cookie"""
        if self.__cookie is not None:
            self.__headers.update({"cookie": self.__cookie})

    def registered_plugin(self):
        """注册插件"""
        for i in os.listdir('.\\plugin'):
            if i.split('.')[-1] == 'py':
                self.plugin.append(i.split('.')[-1])

    def go(self):
        """启动器"""
        self.__chuck()
        try:
            self._get_response_headers()
            self._get_file_type()
            self._get_file_size()
            self._chuck_thread()
            if self.__name is None:
                self._get_file_name()
        except Exception as e:
            print(e)
            return
        self._create_file()
        self._welcome()
        if not self.__is_thread:
            self.__thread = 1
            """判断文件类型启动相应的下载器"""
        if self.__file_type in self.__type:
            self._text_download()
            self.__flag = True
        else:
            self._start_thread()
            self.__flag = True
        if self.__isMd5:
            self._chuck_md5()


if __name__ == '__main__':
    url1 = "https://down.qq.com/qqweb/PCQQ/PCQQ_EXE/PCQQ2020.exe"
    down = Down()
    down.set_url(url1)
    # down.set_filename("1.m4s")
    down.set_isMd5(False)
    down.go()
