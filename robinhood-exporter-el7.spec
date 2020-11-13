Name:	  robinhood-exporter
Version:  0.0.5
%global gittag 0.0.5
Release:  1%{?dist}
Summary:  Prometheus exporter for Robinhood stats on Lustre

License:  Apache License 2.0
URL:      https://github.com/guilbaults/robinhood-exporter
Source0:  https://github.com/guilbaults/%{name}/archive/v%{gittag}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:	systemd
Requires:       python3
Requires:       python3-pip

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

sed -i -e '1i#!/usr/bin/python3.6' robinhood-exporter.py
install -m 0755 %{name}.py %{buildroot}/%{_bindir}/%{name}
install -m 0644 robinhood-exporter.service %{buildroot}/%{_unitdir}/robinhood-exporter.service

%clean
rm -rf $RPM_BUILD_ROOT

%files
%{_bindir}/%{name}
%{_unitdir}/robinhood-exporter.service

%changelog
* Fri Nov 13 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.5-1
- Moving long file heat queries in the background and adding stats for changelog processing
* Fri Nov  6 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.4-1
- Using python3, direct mysql access and pathos for multiprocessing
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.3-1
- Cannot use a dot in a label and fixing parsing of rbh-report
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.2-1
- Adding config path to robinhood's config
* Fri Aug 28 2020 Simon Guilbault <simon.guilbault@calculquebec.ca> 0.0.1-1
- Initial release
