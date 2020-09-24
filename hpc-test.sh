#!/bin/bash
# hpc-testing
# Copyright (C) 2020 SUSE LLC
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

DEFAULT_START_PHASE=0
DEFAULT_END_PHASE=999
DEFAULT_MPI_FLAVOURS="mvapich2,mpich,openmpi3"
DEFAULT_IPPORT1=eth0
DEFAULT_IPPORT2=eth0

export START_PHASE=${START_PHASE:-$DEFAULT_START_PHASE}
export END_PHASE=${END_PHASE:-$DEFAULT_END_PHASE}
export MPI_FLAVOURS=${MPI_FLAVOURS:-$DEFAULT_MPI_FLAVOURS}
export IPPORT1=${IPPORT1:-$DEFAULT_IPPORT1}
export IPPORT2=${IPPORT2:-$DEFAULT_IPPORT2}
export HOST1=
export HOST2=
export DO_MAD=0
export IN_VM=0

source $(dirname $0)/helpers/common.sh
load_helpers $(dirname $0) "common"
load_helpers $(dirname $0) "hpc"

usage(){
	echo "Usage: ${0} [options] <host1> <host2>"
	echo "Options:"
	echo "  -h, --help                     Display usage"
	echo "  -s, --start-phase              Phase to start from (default is $DEFAULT_START_PHASE)"
	echo "  -e, --end-phase                Phase to stop at (default is $DEFAULT_END_PHASE)"
	echo "  -p, --phase <#phase>           Launch only this phase"
	echo "  -v, --verbose                  Display test logs in console."
	echo "      --eth1 <ifname>            Name of the IP interface to setup/use for RXE on host1 (default is $DEFAULT_IPPORT1)"
	echo "      --eth2 <ifname>            Name of the IP interface to setup/use for RXE on host2 (default is $DEFAULT_IPPORT2)"
	echo "  -M, --mpi <mpi>[,<mpi>...]     Comma separated list of MPI flavours to test (default is $DEFAULT_MPI_FLAVOURS)"
	echo "      --in-vm                    Test is being run in a virtual machine"
}

while [ $# -ne 0 ]; do
	case $1 in
		-s|--start-phase)
			START_PHASE=$2
			shift
			;;
		-e|--end-phase)
			END_PHASE=$2
			shift
			;;
		-p|--phase)
			START_PHASE=$2
			END_PHASE=$2
			shift
			;;
		-v|--verbose)
			VERBOSE=1
			;;
		--eth1)
			IPPORT1=$2
			shift
			;;
		--eth2)
			IPPORT2=$2
			shift
			;;
		-M|--mpi)
			MPI_FLAVOURS=$2
			shift
			;;
		--in-vm)
			IN_VM=1
			;;
		--help|-h)
			usage $0
			exit 1
			;;
		[0-9]*.[0-9]*.[0-9]*.[0-9]*)
			if [ "$HOST1" == "" ]; then
				HOST1=$1
			elif [ "$HOST2" == "" ]; then
				HOST2=$1
			else
				fatal_error "Too many host ip provided '$2'"
			fi
			;;
		*)
			fatal_error "Unknow argument $1"
			;;
	esac
	shift
done
if [ "$HOST1" == "" -o "$HOST2" == "" ]; then
	usage $0
	fatal_error "Missing host names"
fi

juLogSetProperty host1.name $HOST1
juLogSetProperty host2.name $HOST2

#########################
#
# Phase 0: State cleanup
# - Install required packages
# - Reset everything needed to mimic an after-reboot run
#
#########################
phase_0(){
	juLog_fatal -name=h1_setup_requirements "setup_requirements $HOST1"
	juLog_fatal -name=h2_setup_requirements "setup_requirements $HOST2"

	juLog -name=h1_firewall_down "firewall_down $HOST1"
	juLog -name=h2_firewall_down "firewall_down $HOST2"
}
run_phase 0 phase_0 "State Cleanup"

set_properties $HOST1
set_properties $HOST2

#########################
#
# Phase 20: HPC
#
#########################
phase_20(){
	tmp=$(cpuid -v);
	juLog -name="CPUID version: $tmp" cpuid -v
	tmp=$(cpuid -1 | sed -n 2,5p);
	juLog -name="CPUID: $tmp" cpuid -1
}
run_phase 20 phase_20 "HPC"
