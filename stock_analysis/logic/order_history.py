from collections import defaultdict
from collections import namedtuple
import datetime
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.order_history import OrderHistory
from database import db


Order = namedtuple('Order', ['user_id', 'order_type', 'ticker', 'date', 'num_shares', 'price'])
TickerShareCount = namedtuple('TickerShares', ['ticker', 'num_shares'])
TickerDate = namedtuple('TickerDate', ['ticker', 'date'])
Session = sessionmaker(bind=db.engine)

BUY_ORDER_TYPE = 'B'
SELL_ORDER_TYPE = 'S'


class OrderHistoryLogic(object):

    def add_orders(self, orders):
        session = Session()
        for order in orders:
            session.add(
                OrderHistory(
                    user_id=order.user_id,
                    order_type=order.order_type,
                    date=order.date,
                    ticker=order.ticker,
                    num_shares=order.num_shares,
                    price=order.price,
                )
            )
        session.commit()

    def get_tickers_and_min_dates_for_user(self, user_id):
        session = Session()
        resp = session.query(OrderHistory.ticker, func.min(OrderHistory.date))\
            .filter_by(user_id=user_id)\
            .group_by(OrderHistory.ticker)\
            .all()
        ticker_dates = [
            TickerDate(x[0], datetime.datetime.strptime(x[1], '%Y-%m-%d').date())
            for x in resp
        ]
        session.close()
        return ticker_dates

    def get_all_order_tickers_min_date(self):
        session = Session()
        resp = session.query(OrderHistory.ticker, func.min(OrderHistory.date))\
            .group_by(OrderHistory.ticker)\
            .all()
        ticker_dates = [
            TickerDate(x[0], datetime.datetime.strptime(x[1], '%Y-%m-%d').date())
            for x in resp
        ]
        session.close()
        return ticker_dates

    def get_orders_for_user(self, user_id):
        session = Session()
        results = session.query(OrderHistory)\
            .filter_by(user_id=user_id)\
            .all()
        session.close()
        return [
            Order(
                user_id=r.user_id,
                order_type=r.order_type,
                ticker=r.ticker,
                date=self._make_date_from_isoformatted_string(r.date),
                num_shares=r.num_shares,
                price=r.price,
            )
            for r in results
        ]

    def get_portfolio_shares_owned_on_date(self, user_id, date):
        session = Session()
        results = session.execute(
            """
            SELECT
                        ticker,
                        SUM(
                            CASE
                                WHEN order_type = 'B' THEN num_shares
                                WHEN order_type = 'S' THEN -1 * num_shares
                            END
                        ) as num_shares
            FROM
                        order_history
            WHERE
                        user_id = :user_id AND
                        date <= :date
            GROUP BY
                        ticker
            ORDER BY
                        ticker
            """,
            {'user_id': user_id, 'date': date.isoformat()},
        ).fetchall()
        session.close()

        return {x[0]: x[1] for x in results}

    def get_ticker_to_orders(self, user_id):
        order_info = defaultdict(list)
        orders = self.get_orders_for_user(user_id)
        for order in orders:
            order_info[order.ticker].append(order)
        return order_info

    def get_ticker_total_purchased_sold(self, user_id):
        ticker_to_orders = self.get_ticker_to_orders(user_id)
        ticker_to_purchased_value = {}
        ticker_to_sold_value = {}
        for ticker, orders in ticker_to_orders.items():
            ticker_to_purchased_value[ticker] = sum(
                o.num_shares * o.price for o in orders if o.order_type == BUY_ORDER_TYPE
            )
            ticker_to_sold_value[ticker] = sum(
                o.num_shares * o.price for o in orders if o.order_type == SELL_ORDER_TYPE
            )
        return ticker_to_purchased_value, ticker_to_sold_value

    # TODO move to logic helper
    def _make_date_from_isoformatted_string(self, date_str):
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
