#!/bin/bash
# hpc-testing
# Copyright (C) 2018 SUSE LLC
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

DEFAULT_START_PHASE=0
DEFAULT_END_PHASE=999
DEFAULT_IPPORT1=eth0
DEFAULT_IPPORT2=eth0

export START_PHASE=${START_PHASE:-$DEFAULT_START_PHASE}
export END_PHASE=${END_PHASE:-$DEFAULT_END_PHASE}
export IPPORT1=${IPPORT1:-$DEFAULT_IPPORT1}
export IPPORT2=${IPPORT2:-$DEFAULT_IPPORT2}
export HOST1=
export HOST2=
export DO_MAD=0
export IN_VM=0

source $(dirname $0)/helpers/common.sh
load_helpers $(dirname $0) "common"
load_helpers $(dirname $0) "rxe"

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
juLogSetProperty $HOST1.rxe_eth $IPPORT1
juLogSetProperty $HOST2.rxe_eth $IPPORT2

#########################
#
# Phase 1: Fabric init
# - SSH known key setup to as some tests will fail if
#   hosts do not know each other
# - Device status check
#
#########################
# Do not wrap these as they export needed variables
get_port $HOST1 1
get_port $HOST2 2

phase_1(){
	juLog_fatal -name=h1_setup_ssh_keys "setup_ssh $HOST1 $IP2"
	juLog_fatal -name=h2_setup_ssh_keys "setup_ssh $HOST2 $IP1"

	juLog_fatal -name=h1_ibvinfo tp $HOST1 ibv_devinfo
	juLog_fatal -name=h2_ibvinfo tp $HOST2 ibv_devinfo

}
run_phase 1 phase_1 "Fabric init"

#########################
#
# Phase 2: Not Applicable
#
#########################
#########################
#
# Phase 3: Not Applicable
#
#########################
#########################
#
# Phase 5: NFSoRDMA
#
#########################
phase_5(){
	true
	#juLog -name=nfs_over_rdma test_nfs $HOST1 $IP1 $HOST2
}
run_phase 5 phase_5 "NFSoRDMA"

#########################
#
# Phase 6: DAPL
#
#########################
phase_6(){
	true
	#juLog -name=dapl -error='DAT_' test_dapl $HOST1 $IPPORT1 $HOST2 $IPPORT2 $IP2
}
run_phase 6 phase_6 "DAPL"

#########################
#
# Phase 7: RDMA/Verbs
#
#########################
phase_7(){
	for mode in rc uc ud srq; do
		export IBV_EXTRA_OPTS=""
		if [ "$mode" == "ud" ]; then
			IBV_EXTRA_OPTS="-s 1450"
		fi
		juLog -name=${mode}_pingpong "(
	  	  test_ibv_pingpong ibv_${mode}_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2 &&
	  	  test_ibv_pingpong ibv_${mode}_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
        )"
	done
}
run_phase 7 phase_7 "RDMA/Verbs"

#########################
#
# Phase 8: MPI
#
#########################
phase_8(){
	FLAVOURS=$(mpi_get_flavors $HOST1 $MPI_FLAVOURS)
	for flavour in $(echo $FLAVOURS | sed -e 's/,/ /g'); do
		juLog -name=mpitests_${flavour} test_mpi ${flavour} $HOST1 $IP1 $IP2
	done
}
run_phase 8 phase_8 "MPI"
