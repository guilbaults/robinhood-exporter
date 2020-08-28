import time
import argparse
import subprocess
import os
import csv
import sys

from prometheus_client.core import REGISTRY, GaugeMetricFamily
from prometheus_client import start_http_server


class RobinhoodCollector(object):
    def __init__(self, fs, config):
        self.fs = fs
        self.config = config

    def collect(self):
        labels = ['filesystem', 'lhsm_status', 'type']
        gauge_count = GaugeMetricFamily(
            'robinhood_count', 'Files count', labels=labels)
        gauge_volume = GaugeMetricFamily(
            'robinhood_volume', 'Files volume', labels=labels)
        gauge_spc_used = GaugeMetricFamily(
            'robinhood_spc_used', 'Files space used', labels=labels)
        gauge_average = GaugeMetricFamily(
            'robinhood_average', 'Files average size', labels=labels)

        DEVNULL = open(os.devnull, 'wb')
        process = subprocess.Popen(['rbh-report', '-f', self.config,
                                   '--status-info', 'lhsm', '--csv'],
                                   stdout=subprocess.PIPE, stderr=DEVNULL)
        out = csv.reader(process.communicate()[0].splitlines()[4:-2])
        for row in out:
            info = ([x.strip() for x in row])
            hsm_status = info[0] or 'none'
            gauge_count.add_metric([self.fs, hsm_status, info[1]], info[2])
            gauge_volume.add_metric([self.fs, hsm_status, info[1]], info[3])
            gauge_spc_used.add_metric([self.fs, hsm_status, info[1]], info[4])
            gauge_average.add_metric([self.fs, hsm_status, info[1]], info[5])
        yield gauge_count
        yield gauge_volume
        yield gauge_spc_used
        yield gauge_average


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
