import argparse
from collections import namedtuple
import csv
import datetime
from sqlalchemy.orm import sessionmaker

from database.order_history import OrderHistory
from database import db


# TODO handle symbols that are sold
blacklisted_tickers = ['UAA', 'UA', 'CASY']

# Not sure why AMT is broken in the api
blacklisted_tickers.append('AMT')


Order = namedtuple('Order', ['ticker', 'date', 'num_shares', 'price'])

class RowParserException(Exception):
    pass


USER_ID=1


Session = sessionmaker(bind=db.engine)


class EtradeIngestor(object):


    def __init__(self):
        self.arg_parser = argparse.ArgumentParser(description='Process an etrade csv file')
        self.arg_parser.add_argument('--csv-path', help='path to csv file')

    def run(self):
        self.args = self.arg_parser.parse_args()
        orders = self.parse_orders_from_csv(self.args.csv_path)
        self.add_orders_to_db(orders)

    def add_orders_to_db(self, orders):
        session = Session()
        for order in orders:
            session.add(
                OrderHistory(
                    user_id=USER_ID,
                    date=order.date,
                    ticker=order.ticker,
                    num_shares=order.num_shares,
                    price=order.price,
                )
            )
        session.commit()

    def parse_orders_from_csv(self, csv_path):
        with open(csv_path) as csv_file:
            reader = csv.reader(csv_file)
            orders = self._parse_orders_from_csv_reader(reader)
            return orders

    def _parse_orders_from_csv_reader(self, reader):
        orders = []
        for row in reader:
            try:
                # Ingore lines that don't parse
                order = self._extract_order_from_row(row)
            except RowParserException:
                continue

            if order:
                orders.append(order)

        return orders

    def _extract_order_from_row(self, row):
        try:
            date = datetime.datetime.strptime(row[0], "%m/%d/%y").date()
            txn_type = row[1]
            ticker = row[3]
            num_shares = int(row[4])
            share_price = float(row[6])
        except Exception:
            raise RowParserException()

        if ticker in blacklisted_tickers or txn_type != 'Bought':
            return None

        return Order(ticker, date, num_shares, share_price)


if __name__ == "__main__":
    EtradeIngestor().run()
