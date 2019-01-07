from py12306.helpers.app import *
from py12306.helpers.func import *
from py12306.log.user_log import UserLog
from py12306.user.job import UserJob


@singleton
class User:
    heartbeat = 60 * 2
    users = []

    def __init__(self):
        self.interval = config.USER_HEARTBEAT_INTERVAL

    @classmethod
    def run(cls):
        self = cls()
        app_available_check()
        self.start()
        pass

    def start(self):
        self.init_users()
        UserLog.print_init_users(users=self.users)
        # 多线程维护用户
        create_thread_and_run(jobs=self.users, callback_name='run', wait=False)

    def init_users(self):
        accounts = config.USER_ACCOUNTS
        for account in accounts:
            user = UserJob(info=account, user=self)
            self.users.append(user)

    @classmethod
    def check_members(cls, members, user_key, call_back):
        """
        检测乘客信息
        :param passengers:
        :return:
        """
        self = cls()

        for user in self.users:
            assert isinstance(user, UserJob)
            if user.key == user_key and user.check_is_ready():
                passengers = user.get_passengers_by_members(members)
                call_back(passengers)
        pass
