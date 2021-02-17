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
        self.long_queries_ready = False
        with open(config) as c:
            content = c.read()
            self.server = re.findall(r'server = (.*);', content)[0]
            self.db_name = re.findall(r'db = (.*);', content)[0]
            self.user = re.findall(r'user = (.*);', content)[0]
            password_file = re.findall(r'password_file = (.*);', content)[0]
            with open(password_file) as pf:
                self.password = pf.read().strip()
            if 'includes/lhsm.inc' in content:
                self.lhsm_enabled = True
            else:
                self.lhsm_enabled = False

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

    def none_to_int(self, results):
        for i in ['count', 'size', 'blocks']:
            if results[i] is None:
                results[i] = int(0)
        return results

    def last_access(self, i):
        older_than = int(time.time() - i[1])
        newer_than = int(time.time() - i[2])
        result = self.query("select count(*) as count,sum(size) as size, \
sum(blocks) as blocks from ENTRIES where last_access \
BETWEEN {} AND {}".format(newer_than, older_than))[0]
        result['range'] = i[0]
        return self.none_to_int(result)

    def last_mod(self, i):
        older_than = int(time.time() - i[1])
        newer_than = int(time.time() - i[2])
        result = self.query("select count(*) as count,sum(size) as size, \
sum(blocks) as blocks from ENTRIES where last_mod \
BETWEEN {} AND {}".format(newer_than, older_than))[0]
        result['range'] = i[0]
        return self.none_to_int(result)

    def size_hist(self, i):
        result = self.query("select count(*) as count,sum(size) as size, \
sum(blocks) as blocks from ENTRIES where size \
BETWEEN {} AND {}".format(i[1], i[2]))[0]
        result['range'] = i[0]
        return self.none_to_int(result)

    def collect(self):
        changelog_count = GaugeMetricFamily(
            'robinhood_changelog_count', 'Changelog count',
            labels=['filesystem', 'mdt', 'type'])
        changelog_last = GaugeMetricFamily(
            'robinhood_changelog_last_number', 'Changelog last action number',
            labels=['filesystem', 'mdt', 'type'])
        changelog_last_recv = GaugeMetricFamily(
            'robinhood_changelog_last_received',
            'Changelog last action received',
            labels=['filesystem', 'mdt', 'type'])
        changelog_last_proc = GaugeMetricFamily(
            'robinhood_changelog_last_processed',
            'Changelog last action processed',
            labels=['filesystem', 'mdt', 'type'])

        vars_q = self.query('select varname, value from VARS')
        for v in vars_q:
            if v['varname'].startswith('CL_Count_'):
                cl_info = v['varname'].split('_')
                changelog_count.add_metric(
                    [self.fs, cl_info[2], cl_info[3]], v['value'])
            if v['varname'].startswith('CL_Last'):
                last = v['varname'][7:].split('_')
                value = v['value'].split(':')

                changelog_last.add_metric(
                    [self.fs, last[1], last[0]], value[0])
                changelog_last_recv.add_metric(
                    [self.fs, last[1], last[0]], value[1])
                changelog_last_proc.add_metric(
                    [self.fs, last[1], last[0]], value[2])

        yield changelog_count
        yield changelog_last
        yield changelog_last_recv
        yield changelog_last_proc

        if self.lhsm_enabled:
            labels = ['filesystem', 'lhsm_status', 'type']
            gauge_count = GaugeMetricFamily(
                'robinhood_count', 'Files count', labels=labels)
            gauge_volume = GaugeMetricFamily(
                'robinhood_volume', 'Files volume', labels=labels)
            gauge_spc_used = GaugeMetricFamily(
                'robinhood_spc_used', 'Files space used', labels=labels)

            stats = self.query("select sum(count) as count,sum(size) as size, \
sum(blocks) as blocks,lhsm_status,type from ACCT_STAT \
group by lhsm_status,type")
            for row in stats:
                if row['lhsm_status'] == '':
                    row['lhsm_status'] = 'none'
                gauge_count.add_metric(
                    [self.fs, row['lhsm_status'], row['type']], row['count'])
                gauge_volume.add_metric(
                    [self.fs, row['lhsm_status'], row['type']], row['size'])
                gauge_spc_used.add_metric(
                    [self.fs, row['lhsm_status'], row['type']], row['blocks'])
            yield gauge_count
            yield gauge_volume
            yield gauge_spc_used

        if self.long_queries_ready:
            # only add them if ready, skip otherwise for faster results
            labels = ['filesystem', 'range']
            gauge_count_heat_atime = GaugeMetricFamily(
                'robinhood_count_heat_last_access',
                'Files count heat by last access date range',
                labels=labels)
            gauge_volume_heat_atime = GaugeMetricFamily(
                'robinhood_volume_heat_last_access',
                'Files volume heat by last access date range',
                labels=labels)
            gauge_spc_used_heat_atime = GaugeMetricFamily(
                'robinhood_spc_used_heat_last_access',
                'Files space used heat by last access date range',
                labels=labels)
            gauge_count_heat_mtime = GaugeMetricFamily(
                'robinhood_count_heat_last_mod',
                'Files count heat by last modification date range',
                labels=labels)
            gauge_volume_heat_mtime = GaugeMetricFamily(
                'robinhood_volume_heat_last_mod',
                'Files volume heat by last modification date range',
                labels=labels)
            gauge_spc_used_heat_mtime = GaugeMetricFamily(
                'robinhood_spc_used_heat_last_mod',
                'Files space used heat by last modification date range',
                labels=labels)
            gauge_count_size_hist = GaugeMetricFamily(
                'robinhood_count_size_hist',
                'Files count by size range',
                labels=labels)
            gauge_volume_size_hist = GaugeMetricFamily(
                'robinhood_volume_size_hist',
                'Files volume by size range',
                labels=labels)
            gauge_spc_used_size_hist = GaugeMetricFamily(
                'robinhood_spc_used_size_hist',
                'Files space by size',
                labels=labels)

            for item in self.last_access_map:
                gauge_count_heat_atime.add_metric(
                    [self.fs, item['range']], item['count'])
                gauge_volume_heat_atime.add_metric(
                    [self.fs, item['range']], item['size'])
                gauge_spc_used_heat_atime.add_metric(
                    [self.fs, item['range']], item['blocks'])
            for item in self.last_mod_map:
                gauge_count_heat_mtime.add_metric(
                    [self.fs, item['range']], item['count'])
                gauge_volume_heat_mtime.add_metric(
                    [self.fs, item['range']], item['size'])
                gauge_spc_used_heat_mtime.add_metric(
                    [self.fs, item['range']], item['blocks'])
            for item in self.last_size_map:
                gauge_count_size_hist.add_metric(
                    [self.fs, item['range']], item['count'])
                gauge_volume_size_hist.add_metric(
                    [self.fs, item['range']], item['size'])
                gauge_spc_used_size_hist.add_metric(
                    [self.fs, item['range']], item['blocks'])

            yield gauge_count_heat_atime
            yield gauge_volume_heat_atime
            yield gauge_spc_used_heat_atime
            yield gauge_count_heat_mtime
            yield gauge_volume_heat_mtime
            yield gauge_spc_used_heat_mtime
            yield gauge_count_size_hist
            yield gauge_volume_size_hist
            yield gauge_spc_used_size_hist

            self.long_queries_ready = False

    def update_long_queries(self):
        date_ranges = [
            ('00s-15m', 0, 15*60),
            ('15m-01h', 15*60, 60*60),
            ('01h-06h', 60*60, 6*60*60),
            ('06h-01d', 6*60*60, 24*60*60),
            ('01d-07d', 24*60*60, 7*24*60*60),
            ('07d-30d', 7*24*60*60, 30*24*60*60),
            ('30d-60d', 30*24*60*60, 60*24*60*60),
            ('60d-6M', 60*24*60*60, 6*30*24*60*60),
            ('6M-1Y', 6*30*24*60*60, 365*24*60*60),
            ('1Y-2Y', 365*24*60*60, 2*365*24*60*60),
            ('2Y-3Y', 2*365*24*60*60, 3*365*24*60*60),
            ('>3Y', 3*365*24*60*60, 10*365*24*60*60),
        ]

        size_ranges = [
            ('0B', 0, 0),
            ('1B-10B', 1, 10**1),
            ('10B-100B', 10**1, 10**2),
            ('1kB-10kB', 10**3 + 1, 10**4),
            ('10kB-100kB', 10**4 + 1, 10**5),
            ('100kB-1MB', 10**5 + 1, 10**6),
            ('1MB-10MB', 10**6 + 1, 10**7),
            ('10MB-100MB', 10**7 + 1, 10**8),
            ('100MB-1GB', 10**8 + 1, 10**9),
            ('1GB-10GB', 10**9 + 1, 10**10),
            ('10GB-100GB', 10**10 + 1, 10**11),
            ('100GB-1TB', 10**11 + 1, 10**12),
            ('1TB-10TB', 10**12 + 1, 10**13),
            ('10TB-100TB', 10**13 + 1, 10**14),
            ('100TB-1PB', 10**14 + 1, 10**15),
            ('1PB+', 10**15 + 1, 10**20),
        ]

        with Pool(processes=40) as pool:
            self.last_access_map = pool.map(self.last_access, date_ranges)
            self.last_mod_map = pool.map(self.last_mod, date_ranges)
            self.last_size_map = pool.map(self.size_hist, size_ranges)
        self.long_queries_ready = True


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
    rbh_collector = RobinhoodCollector(fs, config)
    REGISTRY.register(rbh_collector)
    rbh_collector.update_long_queries()
    while True:
        time.sleep(3600)
        rbh_collector.update_long_queries()
