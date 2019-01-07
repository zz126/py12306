from py12306.helpers.api import LEFT_TICKETS
from py12306.helpers.station import Station
from py12306.log.query_log import QueryLog
from py12306.helpers.func import *
from py12306.log.user_log import UserLog
from py12306.user.user import User


class Job:
    """
    查询任务
    """

    left_dates = []
    left_station = ''
    arrive_station = ''
    left_station_code = ''
    arrive_station_code = ''

    account_key = 0
    allow_seats = []
    allow_train_numbers = []
    members = []
    member_num = 0
    member_num_take = 0  # 最终提交的人数
    passengers = []
    allow_less_member = False

    interval = {}

    query = None
    ticket_info = {}
    INDEX_TICKET_NUM = 11
    INDEX_TRAIN_NUMBER = 3
    INDEX_LEFT_DATE = 13
    INDEX_LEFT_STATION = 6  # 4 5 始发 终点
    INDEX_ARRIVE_STATION = 7
    INDEX_ORDER_TEXT = 1  # 下单文字

    def __init__(self, info, query):
        self.left_dates = info.get('left_dates')
        self.left_station = info.get('stations').get('left')
        self.arrive_station = info.get('stations').get('arrive')
        self.left_station_code = Station.get_station_key_by_name(self.left_station)
        self.arrive_station_code = Station.get_station_key_by_name(self.arrive_station)

        self.account_key = info.get('account_key')
        self.allow_seats = info.get('seats')
        self.allow_train_numbers = info.get('train_numbers')
        self.members = info.get('members')
        self.member_num = len(self.members)
        self.member_num_take = self.member_num
        self.allow_less_member = bool(info.get('allow_less_member'))

        self.interval = query.interval
        self.query = query

    def run(self):
        self.start()

    def start(self):
        """
        处理单个任务
        根据日期循环查询

        展示处理时间
        :param job:
        :return:
        """
        if not self.passengers:
            User.check_members(self.members, self.account_key, call_back=self.set_passengers)

        QueryLog.print_job_start()
        for date in self.left_dates:
            response = self.query_by_date(date)
            self.handle_response(response)
            self.safe_stay()
            if is_main_thread():
                QueryLog.flush(sep='\t\t')
            else:
                QueryLog.add_log('\n')
        if is_main_thread():
            QueryLog.add_quick_log('').flush()
        else:
            QueryLog.flush(sep='\t\t')

    def query_by_date(self, date):
        """
        通过日期进行查询
        :return:
        """
        QueryLog.add_log(QueryLog.MESSAGE_QUERY_START_BY_DATE.format(date, self.left_station, self.arrive_station))
        url = LEFT_TICKETS.get('url').format(left_date=date, left_station=self.left_station_code,
                                             arrive_station=self.arrive_station_code, type='leftTicket/queryZ')

        return self.query.session.get(url)

    def handle_response(self, response):
        """
        错误判断
        余票判断
        小黑屋判断
        座位判断
        乘车人判断
        :param result:
        :return:
        """
        results = self.get_results(response)
        if not results:
            return False
        for result in results:
            self.ticket_info = ticket_info = result.split('|')
            if not self.is_trains_number_valid(ticket_info):  # 车次是否有效
                continue
            QueryLog.add_log(QueryLog.MESSAGE_QUERY_LOG_OF_EVERY_TRAIN.format(self.get_info_of_train_number(),
                                                                              self.get_info_of_ticket_num()))
            if not self.is_has_ticket(ticket_info):
                continue
            allow_seats = self.allow_seats if self.allow_seats else list(config.SEAT_TYPES.values())  # 未设置 则所有可用
            self.handle_seats(allow_seats, ticket_info)

    def handle_seats(self, allow_seats, ticket_info):
        for seat in allow_seats:  # 检查座位是否有票
            ticket_of_seat = ticket_info[get_seat_number_by_name(seat)]
            if not self.is_has_ticket_by_seat(ticket_of_seat):  # 座位是否有效
                continue
            QueryLog.print_ticket_seat_available(left_date=self.get_info_of_left_date(),
                                                 train_number=self.get_info_of_train_number(), seat_type=seat,
                                                 rest_num=ticket_of_seat)
            if not self.is_member_number_valid(ticket_of_seat):  # 乘车人数是否有效
                if self.allow_less_member:
                    self.member_num_take = int(ticket_of_seat)
                    QueryLog.print_ticket_num_less_than_specified(ticket_of_seat, self)
                else:
                    QueryLog.add_quick_log(
                        QueryLog.MESSAGE_GIVE_UP_CHANCE_CAUSE_TICKET_NUM_LESS_THAN_SPECIFIED).flush()
                    continue
            # 检查完成 开始提交订单
            QueryLog.print_ticket_available(left_date=self.get_info_of_left_date(),
                                            train_number=self.get_info_of_train_number(),
                                            rest_num=ticket_of_seat)
            print('检查完成 开始提交订单')

    def get_results(self, response):
        """
        解析查询返回结果
        :param response:
        :return:
        """
        if response.status_code != 200:
            QueryLog.print_query_error(response.reason, response.status_code)
        try:
            result_data = response.json().get('data', {})
            result = result_data.get('result', [])
        except:
            pass  # TODO
        return result if result else False

    def is_has_ticket(self, ticket_info):
        return self.get_info_of_ticket_num() == 'Y' and self.get_info_of_order_text() == '预订'

    def is_has_ticket_by_seat(self, seat):
        return seat != '' and seat != '无' and seat != '*'

    def is_trains_number_valid(self, ticket_info):
        if self.allow_train_numbers:
            return self.get_info_of_train_number() in self.allow_train_numbers
        return True

    def is_member_number_valid(self, seat):
        return seat == '有' or self.member_num <= int(seat)

    def safe_stay(self):
        interval = get_interval_num(self.interval)
        QueryLog.add_stay_log(interval)
        stay_second(interval)

    def set_passengers(self, passengers):
        UserLog.print_user_passenger_init_success(passengers)
        self.passengers = passengers

    # 提供一些便利方法
    def get_info_of_left_date(self):
        return self.ticket_info[self.INDEX_LEFT_DATE]

    def get_info_of_ticket_num(self):
        return self.ticket_info[self.INDEX_TICKET_NUM]

    def get_info_of_train_number(self):
        return self.ticket_info[self.INDEX_TRAIN_NUMBER]

    def get_info_of_left_station(self):
        return Station.get_station_name_by_key(self.ticket_info[self.INDEX_LEFT_STATION])

    def get_info_of_arrive_station(self):
        return Station.get_station_name_by_key(self.ticket_info[self.INDEX_ARRIVE_STATION])

    def get_info_of_order_text(self):
        return self.ticket_info[self.INDEX_ORDER_TEXT]
