import time
import argparse
import os
import sys
import re
import pymysql
from pathos.multiprocessing import ProcessingPool as Pool

from prometheus_client.core import REGISTRY, GaugeMetricFamily
from prometheus_client import start_http_server


class RobinhoodCollector(object):
    def __init__(self, fs, config):
        self.fs = fs
        self.config = config
        with open(config) as c:
            content = c.read()
            self.server = re.findall(r'server = (.*);', content)[0]
            self.db_name = re.findall(r'db = (.*);', content)[0]
            self.user = re.findall(r'user = (.*);', content)[0]
            password_file = re.findall(r'password_file = (.*);', content)[0]
            with open(password_file) as pf:
                self.password = pf.read().strip()

    def query(self, sql):
        db = pymysql.connect(
            host=self.server,
            port=3306,
            user=self.user,
            password=self.password,
            db=self.db_name)
        cursor = db.cursor(pymysql.cursors.DictCursor)
        cursor.execute(sql)
        cursor.close()
        return cursor.fetchall()

    def last_access(self, i):
        older_than = int(time.time() - i[1])
        newer_than = int(time.time() - i[2])
        result = self.query("select count(*) as count,sum(size) as size, sum(blocks) as blocks from ENTRIES where last_access BETWEEN {} AND {}".format(newer_than, older_than))[0]
        result['range'] = i[0]
        return result

    def last_mod(self, i):
        older_than = int(time.time() - i[1])
        newer_than = int(time.time() - i[2])
        result = self.query("select count(*) as count,sum(size) as size, sum(blocks) as blocks from ENTRIES where last_mod BETWEEN {} AND {}".format(newer_than, older_than))[0]
        result['range'] = i[0]
        return result

    def collect(self):
        labels = ['filesystem', 'lhsm_status', 'type']
        gauge_count = GaugeMetricFamily(
            'robinhood_count', 'Files count', labels=labels)
        gauge_volume = GaugeMetricFamily(
            'robinhood_volume', 'Files volume', labels=labels)
        gauge_spc_used = GaugeMetricFamily(
            'robinhood_spc_used', 'Files space used', labels=labels)

        stats = self.query("select sum(count) as count,sum(size) as size,sum(blocks) as blocks,lhsm_status,type from ACCT_STAT group by lhsm_status,type")
        for row in stats:
            if row['lhsm_status'] == '':
                row['lhsm_status'] = 'none'
            gauge_count.add_metric([self.fs, row['lhsm_status'], row['type']], row['count'])
            gauge_volume.add_metric([self.fs, row['lhsm_status'], row['type']], row['size'])
            gauge_spc_used.add_metric([self.fs, row['lhsm_status'], row['type']], row['blocks'])
        yield gauge_count
        yield gauge_volume
        yield gauge_spc_used

        date_ranges = [
            ('00s-15m', 0, 15*60),
            ('15m-01h', 15*60, 60*60),
            ('01h-06h', 60*60, 6*60*60),
            ('06h-01d', 6*60*60, 24*60*60),
            ('01d-07d', 24*60*60, 7*24*60*60),
            ('07d-30d', 7*24*60*60, 30*24*60*60),
            ('30d-60d', 30*24*60*60, 60*24*60*60),
            ('60d-90d', 60*24*60*60, 90*24*60*60),
            ('6M-1Y', 6*30*24*60*60, 365*24*60*60),
            ('>1Y', 365*24*60*60, 10*365*24*60*60),
        ]


        labels_heat = ['filesystem', 'range']
        gauge_count_heat_atime = GaugeMetricFamily(
            'robinhood_count_heat_last_access', 'Files count heat by last access date range', labels=labels_heat)
        gauge_volume_heat_atime = GaugeMetricFamily(
            'robinhood_volume_heat_last_access', 'Files volume heat by last access date range', labels=labels_heat)
        gauge_spc_used_heat_atime = GaugeMetricFamily(
            'robinhood_spc_used_heat_last_access', 'Files space used heat by last access date range', labels=labels_heat)
        gauge_count_heat_mtime = GaugeMetricFamily(
            'robinhood_count_heat_last_mod', 'Files count heat by last modification date range', labels=labels_heat)
        gauge_volume_heat_mtime = GaugeMetricFamily(
            'robinhood_volume_heat_last_mod', 'Files volume heat by last modification date range', labels=labels_heat)
        gauge_spc_used_heat_mtime = GaugeMetricFamily(
            'robinhood_spc_used_heat_last_mod', 'Files space used heat by last modification date range', labels=labels_heat)

        with Pool(processes=20) as pool:
            for item in pool.map(self.last_access, date_ranges):
                gauge_count_heat_atime.add_metric([self.fs, item['range']], item['count'])
                gauge_volume_heat_atime.add_metric([self.fs, item['range']], item['size'])
                gauge_spc_used_heat_atime.add_metric([self.fs, item['range']], item['blocks'])
            for item in pool.map(self.last_mod, date_ranges):
                gauge_count_heat_mtime.add_metric([self.fs, item['range']], item['count'])
                gauge_volume_heat_mtime.add_metric([self.fs, item['range']], item['size'])
                gauge_spc_used_heat_mtime.add_metric([self.fs, item['range']], item['blocks'])
        yield gauge_count_heat_atime
        yield gauge_volume_heat_atime
        yield gauge_spc_used_heat_atime
        yield gauge_count_heat_mtime
        yield gauge_volume_heat_mtime
        yield gauge_spc_used_heat_mtime

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Prometheus collector for Robinhood stats')
    parser.add_argument(
        '--port',
        type=int,
        default=8082,
        help='Collector http port, default is 8082')
    parser.add_argument(
        '--fs',
        type=str,
        help='Filesystem name to use in the labels')
    parser.add_argument(
        '--config',
        type=str,
        help='rbh-report config path')

    args = parser.parse_args()
    if 'FS' in os.environ:
        fs = os.environ['FS']
    else:
        if args.fs:
            fs = args.fs
        else:
            print('FS is not defined as a arg or env var')
            sys.exit(1)
    if 'CONFIG' in os.environ:
        config = os.environ['CONFIG']
    else:
        if args.config:
            config = args.config
        else:
            print('CONFIG is not defined as a arg or env var')
            sys.exit(1)

    start_http_server(args.port)
    REGISTRY.register(RobinhoodCollector(fs, config))
    while True:
        time.sleep(1)
