import base64
import contextlib
import hashlib
import json
import re
from abc import *
from unicodedata import normalize

from appium import webdriver
from appium.webdriver.common.mobileby import MobileBy
from selenium.common.exceptions import TimeoutException, \
    NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait

from library.core.TestLogger import TestLogger


class MobileDriver(ABC):

    def __init__(self, alis_name, model_info, command_executor='http://127.0.0.1:4444/wd/hub',
                 desired_capabilities=None, browser_profile=None, proxy=None, keep_alive=False, card_slot=None):
        self._alis = alis_name
        self._model_info = model_info
        self._remote_url = command_executor
        self._desired_caps = self._init_capability(desired_capabilities)
        self._browser_profile = browser_profile
        self._proxy = proxy
        self._keep_alive = keep_alive
        self._card_slot = self._init_sim_card(card_slot)
        self._driver = None
        self.turn_off_reset()

    def __del__(self):
        if self.is_connection_created:
            self.driver.quit()

    @property
    def alis(self):
        return self._alis

    @property
    def model_info(self):
        return self._model_info

    @TestLogger.log('打开通知栏')
    def open_notifications(self):
        """打开通知栏"""
        if self.is_android():
            self.driver.open_notifications()
        else:
            # TODO IOS打开通知栏待实现
            pass

    def back(self):
        """返回"""
        self.driver.back()

    @property
    def driver(self):
        return self._driver

    @abstractmethod
    def total_card_slot(self):
        """卡槽数量，例如: 1、2"""
        raise NotImplementedError("This method must be implemented!")

    @staticmethod
    def _init_capability(caps):
        return caps

    def _init_sim_card(self, card_slot):
        """初始化手机SIM"""
        cards = []
        if not isinstance(card_slot, list):
            raise Exception('数据类型异常')
        for n in range(self.total_card_slot()):
            if n < len(card_slot):
                card = card_slot[n]
                if isinstance(card, dict):
                    if card['TYPE'] in self.supported_card_types():
                        cards.append(card)
                    else:
                        raise Exception('该手机不支持' + card_slot[n]['TYPE'] + '类型SIM卡（支持类型：{}）'
                                        .format(self.supported_card_types()))
        return cards

    @TestLogger.log('获取指定运营商类型的手机卡（不传类型返回全部配置的手机卡）')
    def get_cards(self, card_type=None):
        """返回指定类型卡手机号列表"""
        cards = [card for card in self._card_slot if card is not None]
        if card_type is None:
            return list(
                [card.get('CARD_NUMBER') for card in cards]
            )
        if not isinstance(card_type, list):
            card_type = [card_type]
        return list(
            [card.get('CARD_NUMBER') for card in self._card_slot if (card is not None) and (card['TYPE'] in card_type)]
        )

    @TestLogger.log('获取手机卡号')
    def get_card(self, index):
        """
        获取手机卡信息
        :param index: 卡槽位置
        :return: 号码、运营商类型
        """
        return self._card_slot[index].get('CARD_NUMBER'), self._card_slot[index].get('TYPE')

    @abstractmethod
    def supported_card_types(self):
        """返回手机卡支持类型列表"""
        raise NotImplementedError("This method must be implemented!")

    @property
    def is_connection_created(self):
        if self.driver is None:
            return False
        else:
            try:
                t = self.driver.current_package
                return True
            except Exception:  # InvalidSessionIdException or WebDriverException:
                return False

    @TestLogger.log('连接到手机')
    def connect_mobile(self):
        if self.driver is None:
            try:
                self._driver = webdriver.Remote(self._remote_url, self._desired_caps, self._browser_profile,
                                                self._proxy,
                                                self._keep_alive)
            except Exception as e:
                raise RuntimeError('无法连接到 appium server: {}'.format(self._remote_url))
        elif not self.is_connection_created:
            try:
                self.driver.start_session(self._desired_caps)
            except Exception as e:
                raise RuntimeError('无法连接到 appium server: {}'.format(self._remote_url))
        else:
            return

    @TestLogger.log('断开手机连接')
    def disconnect_mobile(self):
        if self.is_connection_created:
            self.driver.quit()

    @TestLogger.log('打开重置APP选项（仅当手机未连接时有效）')
    def turn_on_reset(self):
        """开启重置app（在获取session之前有效）"""
        self._desired_caps['noReset'] = False

    # @TestLogger.log('关闭重置APP选项（仅当手机未连接时有效）')
    def turn_off_reset(self):
        """关闭重置app（在获取session之前有效）"""
        self._desired_caps['noReset'] = True

    @TestLogger.log('判断当前设备与传入平台名是否一致')
    def is_platform(self, platform):
        if self.is_connection_created:
            platform_name = self.driver.desired_capabilities['platformName']
        else:
            platform_name = self._desired_caps['platformName']
        return platform.lower() == platform_name.lower()

    @TestLogger.log('判断当前设备是否为IOS设备')
    def is_ios(self):
        return self.is_platform('ios')

    @TestLogger.log('判断当前设备是否为Android设备')
    def is_android(self):
        return self.is_platform('android')

    @TestLogger.log('启动默认APP')
    def launch_app(self):
        self.driver.launch_app()

    @TestLogger.log('强制结束APP进程')
    def terminate_app(self, app_id, **options):
        self.driver.terminate_app(app_id, **options)

    @TestLogger.log('将当前打开的APP后台运行指定时间(S)')
    def background_app(self, seconds):
        self.driver.background_app(seconds)

    @TestLogger.log('激活APP')
    def activate_app(self, app_id):
        self.driver.activate_app(app_id)

    @TestLogger.log('重置当前打开的APP')
    def reset_app(self):
        self.driver.reset()

    @TestLogger.log('点按手机Home键')
    def press_home_key(self):
        """模拟手机HOME键"""
        if self.is_android():
            self.execute_shell_command('input', 'keyevent', 3)
        else:
            raise NotImplementedError('IOS 点击HOME键未实现')

    @TestLogger.log('执行ADB shell命令')
    def execute_shell_command(self, command, *args):
        """
        Execute ADB shell commands (requires server flag --relaxed-security to be set)

        例：execute_shell_command('am', 'start', '-n', 'com.example.demo/com.example.test.MainActivity')

        :param command: 例：am,pm 等等可执行命令
        :param args: 例：am,pm 等可执行命令的参数
        :return:
        """
        script = {
            'command': command,
            'args': args
        }
        result = self.driver.execute_script('mobile:shell', script)
        print(result)
        return result

    @contextlib.contextmanager
    def listen_verification_code(self, max_wait_time=30):
        """监听验证码"""
        context = self._actions_before_send_get_code_request()
        code_container = []
        yield code_container
        code = self._actions_after_send_get_code_request(context, max_wait_time)
        if isinstance(code, list):
            code_container.append(code[0])
        elif isinstance(code, str):
            code_container.append(code)

    def _actions_before_send_get_code_request(self):
        """开始获取验证码之前的动作"""
        try:
            self.execute_shell_command('logcat', '-c')
        except Exception as e:
            print(e.__str__())

    def _actions_after_send_get_code_request(self, context, max_wait_time):
        """开始获取验证码之后的动作，结果为返回的验证码"""
        result = self.wait_until(
            condition=lambda d: re.findall(r'【登录验证】尊敬的用户：(\d+)',
                                           self.execute_shell_command('logcat', '-d', 'appium:D', 'MmsService:W', '*:S')
                                           ),
            timeout=max_wait_time
        )
        if result:
            return result[0]
        raise Exception("手机收不到验证码")

    def wait_until(self, condition, timeout=8, auto_accept_permission_alert=True):
        this = self

        def execute_condition(driver):
            """如果有弹窗，自动允许"""

            def get_accept_permission_handler(d):
                """获取允许权限弹窗的方法句柄"""
                try:
                    alert = d.switch_to.alert
                    return alert.accept
                except:
                    alert = this.get_elements((MobileBy.XPATH, '//android.widget.Button[@text="始终允许" or @text="允许"]'))
                    if not alert:
                        return False
                    return alert[0].click

            if auto_accept_permission_alert:
                if this.driver.current_activity in [
                    'com.android.packageinstaller.permission.ui.GrantPermissionsActivity',
                    '.permission.ui.GrantPermissionsActivity'
                ]:
                    need = True
                    while need:
                        try:
                            WebDriverWait(this.driver, 1).until(
                                get_accept_permission_handler
                            )()
                        except:
                            need = False
            return condition(driver)

        wait = WebDriverWait(self.driver, timeout)
        return wait.until(execute_condition)

    @TestLogger.log('等待条件成功，并监听异常条件')
    def wait_condition_and_listen_unexpected(self, condition, timeout=8,
                                             auto_accept_permission_alert=True, unexpected=None, poll=0.2):
        this = self

        # unexpect = unexpected

        def execute_condition(driver):
            """如果有弹窗，自动允许"""

            def get_accept_permission_handler(d):
                """获取允许权限弹窗的方法句柄"""
                try:
                    alert = d.switch_to.alert
                    return alert.accept
                except:
                    alert = this.get_elements((MobileBy.XPATH, '//android.widget.Button[@text="始终允许" or @text="允许"]'))
                    if not alert:
                        return False
                    return alert[0].click

            if auto_accept_permission_alert:
                if this.driver.current_activity in [
                    'com.android.packageinstaller.permission.ui.GrantPermissionsActivity',
                    '.permission.ui.GrantPermissionsActivity'
                ]:
                    need = True
                    while need:
                        try:
                            WebDriverWait(this.driver, 1).until(
                                get_accept_permission_handler
                            )()
                        except:
                            need = False

            if unexpected:
                if unexpected():
                    raise AssertionError("检查到页面报错")
            return condition(driver)

        wait = WebDriverWait(self.driver, timeout, poll)
        return wait.until(execute_condition)

    @TestLogger.log('获取OS平台名')
    def get_platform(self):
        try:
            platform_name = self.driver.desired_capabilities['platformName']
        except Exception as e:
            raise e
        return platform_name.lower()

    @TestLogger.log('获取设备型号')
    def get_device_model(self):
        """获取设备型号"""
        platform = self.get_platform()
        if platform == 'android':
            model = self.execute_shell_command('getprop', 'ro.product.model')
            return model.strip()
        elif platform == 'ios':
            return 'ios'
        else:
            return 'other'

    @TestLogger.log('获取元素')
    def get_element(self, locator):
        return self.driver.find_element(*locator)

    @TestLogger.log('获取元素列表')
    def get_elements(self, locator):
        return self.driver.find_elements(*locator)

    @TestLogger.log('获取元素文本(支持遍历子元素并返回文本数组)')
    def get_text(self, locator):
        """获取元素文本"""
        self.wait_until(
            condition=lambda d: self.get_elements(locator)
        )
        elements = self.get_elements(locator)
        if len(elements) > 0:
            return elements[0].text
        return None

    @TestLogger.log("获取控件属性")
    def get_element_attribute(self, locator, attr, wait_time=0):
        try:
            widget = self.wait_until(
                condition=lambda d: self.get_element(locator),
                timeout=wait_time
            )
            value = widget.get_attribute(attr)
            return value
        except TimeoutException:
            raise NoSuchElementException("找不到控件：{}".format(locator))

    @TestLogger.log('判断页面是否包含指定文本')
    def is_text_present(self, text):
        text_norm = normalize('NFD', text)
        source_norm = normalize('NFD', self.get_source())
        result = text_norm in source_norm
        return result

    @TestLogger.log('判断元素是否包含在页面DOM')
    def _is_element_present(self, locator):
        elements = self.get_elements(locator)
        return len(elements) > 0

    @TestLogger.log('判断元素是否可见')
    def _is_visible(self, locator):
        elements = self.get_elements(locator)
        if len(elements) > 0:
            return elements[0].is_displayed()
        return None

    @TestLogger.log('判断元素是否可点击')
    def _is_clickable(self, locator):
        mapper = {
            'true': True,
            'false': False,
            'True': True,
            'False': False
        }
        element = self.get_element(locator)
        value = element.get_attribute('clickable')
        is_clickable = mapper[value.lower()]
        return is_clickable

    @TestLogger.log('判断元素文本与期望的模式是否匹配（支持正则）')
    def _is_element_text_match(self, locator, pattern, full_match=True, regex=False):
        element = self.get_element(locator)
        actual = element.text
        if regex:
            if full_match:
                pt = re.compile(pattern)
                result = pt.fullmatch(actual)
            else:
                pt = re.compile(pattern)
                result = pt.search(actual)
        else:
            if full_match:
                result = pattern == actual
            else:
                result = pattern in actual
        if not result:
            return False
        return True

    @TestLogger.log('判断元素是否可用')
    def _is_enabled(self, locator):
        element = self.get_element(locator)
        return element.is_enabled()

    @TestLogger.log('获取页面DOM文档')
    def get_source(self):
        return self.driver.page_source

    @TestLogger.log('点击坐标')
    def tap(self, positions, duration=None):
        self.driver.tap(positions, duration)

    @TestLogger.log('点击元素（默认等待5秒，且等待期间自动允许弹出权限）')
    def click_element(self, locator, default_timeout=5, auto_accept_permission_alert=True):
        self.wait_until(
            condition=lambda d: self.get_element(locator),
            timeout=default_timeout,
            auto_accept_permission_alert=auto_accept_permission_alert
        ).click()
        # self.get_element(locator).click()

    @TestLogger.log('点击文本（支持完全匹配和模糊匹配）')
    def click_text(self, text, exact_match=False):
        if self.get_platform() == 'ios':
            if exact_match:
                _xpath = u'//*[@value="{}" or @label="{}"]'.format(text, text)
            else:
                _xpath = u'//*[contains(@label,"{}") or contains(@value, "{}")]'.format(text, text)
            self.get_element((MobileBy.XPATH, _xpath)).click()
        elif self.get_platform() == 'android':
            if exact_match:
                _xpath = u'//*[@{}="{}"]'.format('text', text)
            else:
                _xpath = u'//*[contains(@{},"{}")]'.format('text', text)
            self.get_element((MobileBy.XPATH, _xpath)).click()

    @TestLogger.log('输入文本')
    def input_text(self, locator, text, default_timeout=5):
        self.wait_until(
            condition=lambda d: self.get_element(locator),
            timeout=default_timeout
        ).send_keys(text)

    @TestLogger.log('勾选可选控件')
    def select_checkbox(self, locator):
        """勾选复选框"""
        if not self.is_selected(locator):
            self.click_element(locator)

    @TestLogger.log('去勾选可选控件')
    def unselect_checkbox(self, locator):
        """去勾选复选框"""
        if self.is_selected(locator):
            self.click_element(locator)

    @TestLogger.log('判断可选控件是否为已选中状态')
    def is_selected(self, locator):
        el = self.get_element(locator)
        result = el.get_attribute("checked")
        if result.lower() == "true":
            return True
        return False

    @TestLogger.log('断言：检查checkbox是否已选中')
    def checkbox_should_be_selected(self, locator):
        # element = self.get_element(locator)
        if not self.is_selected(locator):
            raise AssertionError("Checkbox '{}' should have been selected "
                                 "but was not.".format(locator))
        return True

    @TestLogger.log('断言：检查checkbox是否未选中')
    def checkbox_should_not_be_selected(self, locator):
        # element = self.get_element(locator)
        if self.is_selected(locator):
            raise AssertionError("Checkbox '{}' should not have been selected "
                                 "but was not.".format(locator))
        return True

    @TestLogger.log('点到点滑动')
    def swipe_point_to_point(self, from_position, to_position, duration=None):
        if self.is_android():
            self.driver.swipe(
                from_position[0],
                from_position[1],
                to_position[0],
                to_position[1],
                duration
            )
        else:
            self.driver.swipe(
                from_position[0],
                from_position[1],
                to_position[0] - from_position[0],
                to_position[1] - from_position[1],
                duration
            )

    @TestLogger.log('在控件上按指定的上下左右方向滑动')
    def swipe_by_direction(self, locator, direction, duration=None):
        """
        在元素内滑动
        :param locator: 定位器
        :param direction: 方向（left,right,up,down）
        :param duration: 持续时间ms
        :return:
        """
        if isinstance(locator, (list, tuple)):
            element = self.get_element(locator)
        elif isinstance(locator, WebElement):
            element = locator
        else:
            raise TypeError('Type of {} is not a list like or WebElement'.format(locator))
        rect = element.rect
        left, right = int(rect['x']) + 1, int(rect['x'] + rect['width']) - 1
        top, bottom = int(rect['y']) + 1, int(rect['y'] + rect['height']) - 1
        width = int(rect['width']) - 2
        height = int(rect['height']) - 2

        if self.get_platform() == 'android':
            if direction.lower() == 'left':
                x_start = right
                x_end = left
                y_start = (top + bottom) // 2
                y_end = (top + bottom) // 2
                self.driver.swipe(x_start, y_start, x_end, y_end, duration)
            elif direction.lower() == 'right':
                x_start = left
                x_end = right
                y_start = (top + bottom) // 2
                y_end = (top + bottom) // 2
                self.driver.swipe(x_start, y_start, x_end, y_end, duration)
            elif direction.lower() == 'up':
                x_start = (left + right) // 2
                x_end = (left + right) // 2
                y_start = bottom
                y_end = top
                self.driver.swipe(x_start, y_start, x_end, y_end, duration)
            elif direction.lower() == 'down':
                x_start = (left + right) // 2
                x_end = (left + right) // 2
                y_start = top
                y_end = bottom
                self.driver.swipe(x_start, y_start, x_end, y_end, duration)

        else:
            if direction.lower() == 'left':
                x_start = right
                x_offset = width
                y_start = (top + bottom) // 2
                y_offset = 0
                self.driver.swipe(x_start, y_start, x_offset, y_offset, duration)
            elif direction.lower() == 'right':
                x_start = left
                x_offset = width
                y_start = -(top + bottom) // 2
                y_offset = 0
                self.driver.swipe(x_start, y_start, x_offset, y_offset, duration)
            elif direction.lower() == 'up':
                x_start = (left + right) // 2
                x_offset = 0
                y_start = bottom
                y_offset = -height
                self.driver.swipe(x_start, y_start, x_offset, y_offset, duration)
            elif direction.lower() == 'down':
                x_start = (left + right) // 2
                x_offset = 0
                y_start = top
                y_offset = height
                self.driver.swipe(x_start, y_start, x_offset, y_offset, duration)

    @TestLogger.log('按百分比在屏幕上滑动')
    def swipe_by_percent_on_screen(self, start_x, start_y, end_x, end_y, duration):
        width = self.driver.get_window_size()["width"]
        height = self.driver.get_window_size()["height"]
        x_start = float(start_x) / 100 * width
        x_end = float(end_x) / 100 * width
        y_start = float(start_y) / 100 * height
        y_end = float(end_y) / 100 * height
        x_offset = x_end - x_start
        y_offset = y_end - y_start
        if self.get_platform() == 'android':
            self.driver.swipe(x_start, y_start, x_end, y_end, duration)
        else:
            self.driver.swipe(x_start, y_start, x_offset, y_offset, duration)

    @TestLogger.log('断言：检查页面是否包含文本')
    def assert_screen_contain_text(self, text):
        if not self.is_text_present(text):
            raise AssertionError("Page should have contained text '{}' "
                                 "but did not" % text)

    @TestLogger.log('断言：检查页面是否不包含文本')
    def assert_screen_should_not_contain_text(self, text):
        if self.is_text_present(text):
            raise AssertionError("Page should not have contained text '{}'" % text)

    @TestLogger.log('断言：检查页面是否包含元素')
    def assert_screen_should_contain_element(self, locator):
        if not self._is_element_present(locator):
            raise AssertionError("Page should have contained element '{}' "
                                 "but did not".format(locator))

    @TestLogger.log('断言：检查页面是否不包含元素')
    def assert_should_not_contain_element(self, locator):
        if self._is_element_present(locator):
            raise AssertionError("Page should not have contained element {}".format(locator))

    @TestLogger.log('断言：检查元素是否禁用')
    def assert_element_should_be_disabled(self, locator):
        if self._is_enabled(locator):
            raise AssertionError("Element '{}' should be disabled "
                                 "but did not".format(locator))

    @TestLogger.log('断言：检查元素是否可用')
    def assert_element_should_be_enabled(self, locator):
        if not self._is_enabled(locator):
            raise AssertionError("Element '{}' should be enabled "
                                 "but did not".format(locator))

    @TestLogger.log('断言：检查元素是否可见')
    def assert_element_should_be_visible(self, locator):
        if not self.get_element(locator).is_displayed():
            raise AssertionError("Element '{}' should be visible "
                                 "but did not".format(locator))

    @TestLogger.log('断言：检查元素包含指定文本')
    def assert_element_should_contain_text(self, locator, expected, message=''):
        actual = self.get_text(locator)
        if expected not in actual:
            if not message:
                message = "Element '{}' should have contained text '{}' but " \
                          "its text was '{}'.".format(locator, expected, actual)
            raise AssertionError(message)

    @TestLogger.log('断言：检查元素不包含指定文本')
    def assert_element_should_not_contain_text(self, locator, expected, message=''):
        actual = self.get_text(locator)
        if expected in actual:
            if not message:
                message = "Element {} should not contain text '{}' but " \
                          "it did.".format(locator, expected)
            raise AssertionError(message)

    @TestLogger.log('断言：检查元素文本等于期望值')
    def assert_element_text_should_be(self, locator, expected, message=''):
        element = self.get_element(locator)
        actual = element.text
        if expected != actual:
            if not message:
                message = "The text of element '{}' should have been '{}' but in fact it was '{}'." \
                    .format(locator, expected, actual)
            raise AssertionError(message)

    @TestLogger.log('断言：检查元素文本与模式匹配（支持正则表达式）')
    def assert_element_text_should_match(self, locator, pattern, full_match=True, regex=False):
        """断言元素内文本，支持正则表达式"""
        element = self.get_element(locator)
        actual = element.text
        if regex:
            if full_match:
                pt = re.compile(pattern)
                result = pt.fullmatch(actual)
            else:
                pt = re.compile(pattern)
                result = pt.search(actual)
        else:
            if full_match:
                result = pattern == actual
            else:
                result = pattern in actual
        if not result:
            raise AssertionError(
                "Expect is" + " match regex pattern" if regex else "" + ": " + pattern + "\n"
                                                                   + "Actual is: " + actual + '\n')

    def run_app_in_background(self, seconds=5):
        """让 app 进入后台运行seconds 秒"""
        self.driver.background_app(seconds)

    @TestLogger.log('获取网络状态（不要用，不同机型返回结果不一样，不可控制）')
    def get_network_status(self):
        """获取网络链接状态"""
        return self.driver.network_connection

    @TestLogger.log('设置网络状态')
    def set_network_status(self, status):
        """设置网络
        Connection types are specified here:
        https://code.google.com/p/selenium/source/browse/spec-draft.md?repo=mobile#120
        Value (Alias)      | Data | Wifi | Airplane Mode
        -------------------------------------------------
        0 (None)           | 0    | 0    | 0
        1 (Airplane Mode)  | 0    | 0    | 1
        2 (Wifi only)      | 0    | 1    | 0
        4 (Data only)      | 1    | 0    | 0
        6 (All network on) | 1    | 1    | 0

        class ConnectionType(object):
            NO_CONNECTION = 0
            AIRPLANE_MODE = 1
            WIFI_ONLY = 2
            DATA_ONLY = 4
            ALL_NETWORK_ON = 6
        """
        if status == 0:
            self.turn_off_airplane_mode()
            self.turn_off_mobile_data()
            self.turn_off_wifi()
            return 0
        elif status == 1:
            self.turn_on_airplane_mode()
            return 1
        elif status == 2:
            self.turn_off_airplane_mode()
            self.turn_off_mobile_data()
            self.turn_on_wifi()
            return 2
        elif status == 4:
            self.turn_off_airplane_mode()
            self.turn_on_mobile_data()
            self.turn_off_wifi()
            return 4
        elif status == 6:
            self.turn_off_airplane_mode()
            self.turn_on_wifi()
            self.turn_on_mobile_data()
            return 6
        else:
            raise ValueError(
                """
Value (Alias)      | Data | Wifi | Airplane Mode
-------------------------------------------------
0 (None)           | 0    | 0    | 0
1 (Airplane Mode)  | 0    | 0    | 1
2 (Wifi only)      | 0    | 1    | 0
4 (Data only)      | 1    | 0    | 0
6 (All network on) | 1    | 1    | 0
                """
            )

    @TestLogger.log('推送文件到手机内存')
    def push_file(self, file_path, to_path):
        """推送apk到手机"""
        with open(file_path, 'rb') as f:
            content = f.read()
            mda = hashlib.md5(content).hexdigest()
        b64 = str(base64.b64encode(content), 'UTF-8')
        self.driver.push_file(to_path, b64)
        if self.is_android():
            # 安卓使用shell命令验证MD5
            mdb = self.execute_shell_command('md5sum', '-b', to_path).strip()
            return mda == mdb
        else:
            # TODO IOS MD5验证待实现
            return True

    def is_keyboard_shown(self):
        return self.driver.is_keyboard_shown()

    @TestLogger.log('隐藏键盘')
    def hide_keyboard(self, key_name=None, key=None, strategy=None):
        """隐藏键盘"""
        self.driver.hide_keyboard(key_name, key, strategy)

    @TestLogger.log('发送短信')
    def send_sms(self, to, content, card_index=0):
        """
        发送短信
        :param to: 目标号码
        :param content: 短信内容
        :param card_index: 使用的需要，默认使用第一张卡
        :return:
        """
        if self.is_android():
            self.terminate_app('com.android.mms')
            self.execute_shell_command('am', 'start', '-a', 'android.intent.action.SENDTO', '-d', 'sms:', '-e',
                                       'sms_body', content, '--ez', 'exit_on_sent', 'true')
            self.execute_shell_command('input', 'text', to)
            self.click_element([MobileBy.XPATH, '//*[@content-desc="发送"]'])
            if len(self.get_cards()) > 1:
                locator = [MobileBy.XPATH,
                           '//*[contains(@text,"中国移动") or contains(@text,"中国联通") or contains(@text,"中国电信")]']
                self.wait_until(
                    condition=lambda d: len(self.get_elements(locator)) > card_index
                )
                send_bys = self.get_elements(
                    locator)
                send_bys[card_index].click()
            return self.get_card(card_index)
        elif self.is_ios():
            # TODO IOS发短信功能待实现
            pass
        else:
            pass

    def set_clipboard_text(self, text, label=None):
        self.driver.set_clipboard_text(text, label)

    @TestLogger.log("粘贴")
    def paste(self):
        # TODO
        raise NotImplementedError('该方法未实现')

    def list_iterator(self, scroll_view_locator, item_locator):
        """
        迭代列表内容
        :param scroll_view_locator: 列表容器的定位器
        :param item_locator: 列表项定位器
        :return:
        """
        if self.get_elements(scroll_view_locator):
            scroll_view = self.get_element(scroll_view_locator)
        else:
            return

        items = self.get_elements(item_locator)
        if not items:
            return
        for i in items:

            # 判断元素位置是否已经超过滚动视图的中点
            scroll_view_center = scroll_view.location.get('y') + scroll_view.size.get('height') // 2
            if i.location.get('y') > scroll_view_center:
                pre_y = i.location.get('y')

                # 稳定的滑动最少要在press后保持600ms才能移动
                minimum_hold_time = 600
                self.swipe_by_direction(i, 'up', minimum_hold_time)
                post_y = i.location.get('y')
                if pre_y == post_y:

                    # 坐标没变化就把剩下的抛出去然后结束循环
                    yield from items[items.index(i):]
                    return
                else:

                    # 坐标变化就更新找出的列表
                    restorer = items[:items.index(i)]
                    items.clear()
                    refreshed_items = self.get_elements(item_locator)
                    if not refreshed_items:
                        return
                    for refreshed_item in refreshed_items:
                        if refreshed_item.location.get('y') == post_y:
                            the_rests = refreshed_items[refreshed_items.index(refreshed_item):]
                            restorer.extend(the_rests)
                            break
                    items.extend(restorer)
            yield i
            refreshed_items = self.get_elements(item_locator)
            refreshed_items.reverse()
            for refreshed_item in refreshed_items:
                offset = -1 - refreshed_items.index(refreshed_item)
                if abs(offset) <= len(items):
                    items[offset] = refreshed_item

    @TestLogger.log('开启数据流量')
    def turn_on_mobile_data(self):
        """
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.DATA_ROAMING_SETTINGS 打开移动网络设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.DATA_ROAMING_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'false':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'true',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"true"')
            self.back()
            return True
        elif self.is_ios():
            # TODO IOS系统上的数据流量开关操作未实现
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    @TestLogger.log('关闭数据流量')
    def turn_off_mobile_data(self):
        """
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.DATA_ROAMING_SETTINGS 打开移动网络设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.DATA_ROAMING_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'true':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'false',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"false"')
            self.back()
            return True
        elif self.is_ios():
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    @TestLogger.log('开启WIFI')
    def turn_on_wifi(self):
        """
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.WIFI_SETTINGS 打开WIFI设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.WIFI_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'false':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'true',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"true"')
            # try:
            #     self.wait_until(
            #         condition=lambda d: self.is_text_present('已连接'),
            #         timeout=30,
            #         auto_accept_permission_alert=False
            #     )
            # except TimeoutException:
            #     raise RuntimeError('手机WIFI 已开启，但没有自动连接到 WIFI 热点')
            self.back()
            return True
        elif self.is_ios():
            # TODO IOS系统上的数据流量开关操作未实现
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    @TestLogger.log('关闭WIFI')
    def turn_off_wifi(self):
        """
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.WIFI_SETTINGS 打开WIFI设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.WIFI_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'true':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'false',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"false"')
            self.back()
            return True
        elif self.is_ios():
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    @TestLogger.log('开启飞行模式')
    def turn_on_airplane_mode(self):
        """
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.AIRPLANE_MODE_SETTINGS 打开WIFI设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.AIRPLANE_MODE_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'false':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'true',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"true"')
            self.back()
            return True
        elif self.is_ios():
            # TODO IOS系统上的数据流量开关操作未实现
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    @TestLogger.log('关闭飞行模式')
    def turn_off_airplane_mode(self):
        """
        由于appium set_network_connection接口不靠谱，所有有关网络状态的设置需要在UI层面操作
        Android系统：
            默认使用adb命令 adb shell am start -a android.settings.AIRPLANE_MODE_SETTINGS 打开WIFI设置页，
            通过寻找第一个checkable="true"的控件当做数据开关进行开启、关闭操作
        IOS系统：
            未实现
        如果该方法对正在使用的机型不适用，应该在具体的mobile实现类中重写该方法
        :return:
        """
        if self.is_android():
            params = 'am start -a android.settings.AIRPLANE_MODE_SETTINGS'.split(' ')
            self.execute_shell_command(*params)
            switch_locator = [MobileBy.XPATH, '//*[@checkable="true"]']
            if self.get_element_attribute(switch_locator, 'checked') == 'true':
                self.click_element(switch_locator, auto_accept_permission_alert=False)
            try:
                self.wait_until(
                    condition=lambda d: self.get_element_attribute(switch_locator, 'checked') == 'false',
                    auto_accept_permission_alert=False
                )
            except TimeoutException:
                print(self.get_element_attribute(switch_locator, 'checked'))
                raise RuntimeError('开关的checked属性没有置为"false"')
            self.back()
            return True
        elif self.is_ios():
            raise NotImplementedError('IOS 未实现该操作')
        else:
            raise NotImplementedError('该API不支持android/ios以外的系统')

    def __str__(self):
        device_info = {
            "name": self.alis,
            "model": self.model_info["ReadableName"]
        }
        return json.dumps(device_info, ensure_ascii=False)
