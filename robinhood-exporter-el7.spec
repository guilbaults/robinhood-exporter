Name:	  robinhood-exporter
Version:  0.0.3
%global gittag 0.0.3
Release:  1%{?dist}
Summary:  Prometheus exporter for Robinhood stats on Lustre

License:  Apache License 2.0
URL:      https://github.com/guilbaults/robinhood-exporter
Source0:  https://github.com/guilbaults/%{name}/archive/v%{gittag}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:	systemd
Requires:       python2-prometheus_client

%description
Prometheus exporter for Robinhood stats on Lustre
https://github.com/cea-hpc/robinhood/

%prep
%autosetup -n %{name}-%{gittag}
%setup -q

%build

%install
mkdir -p %{buildroot}/%{_bindir}
mkdir -p %{buildroot}/%{_unitdir}

sed -i -e '1i#!/usr/bin/python' robinhood-exporter.py
install -m 0755 %{name}.py %{buildroot}/%{_bindir}/%{name}
install -m 0644 robinhood-exporter.service %{buildroot}/%{_unitdir}/robinhood-exporter.service

%clean
rm -rf $RPM_BUILD_ROOT

%files
%{_bindir}/%{name}
%{_unitdir}/robinhood-exporter.service

%changelog
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.3-1
- Cannot use a dot in a label and fixing parsing of rbh-report
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.2-1
- Adding config path to robinhood's config
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.1-1
- Initial release
