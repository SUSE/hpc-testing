#
# spec file for package hpc-testing
#
# Copyright (c) 2017 SUSE LINUX GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#

%define git_ver %{nil}

Name:           hpc-testing
Version:        0.1
Release:        0
Summary:        Test scripts to validate HPC packages
License:        GPL-3.0
Group:          Development/Tools/Other
Url:            https://github.com/nmorey/git-sequencer-status
Source:         %{name}-%{version}%{git_ver}.tar.bz2
Requires:       libibverbs
Requires:       libfabric
Requires:       opensm
Requires:       rdma-ndd
Requires:       infiniband-diags
Requires:       libibverbs-utils
Requires:       srp_daemon
Requires:       fabtests
Requires:       mpitests-mvapich2
Requires:       mpitests-openmpi
Requires:       mpitests-openmpi2
Requires:       mpitests-mpich
Requires:       mpitests
Requires:       ibutils
BuildArch:      noarch

%description
QA test suite for Infiniband and OmniPath validation

%prep
%setup -q -n %{name}-%{version}%{git_ver}

%build

%check

%install
install -D -m 0755 ib-test.sh %{buildroot}/%{_datadir}/%{name}/ib-test.sh
cp -R helpers %{buildroot}/%{_datadir}/%{name}/

%files
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/ib-test.sh
%{_datadir}/%{name}/helpers

%changelog
