#!/bin/bash
spectool -g -R robinhood-exporter-el7.spec
rpmbuild --define "dist .el7" -ba robinhood-exporter-el7.spec
