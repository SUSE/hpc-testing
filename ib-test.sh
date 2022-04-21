#!/bin/bash
# hpc-testing
# Copyright (C) 2022 SUSE LLC
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
DEFAULT_IP1=192.168.0.1
DEFAULT_IP2=192.168.0.2
DEFAULT_IPOIB_MODES="connected,datagram"

export START_PHASE=${START_PHASE:-$DEFAULT_START_PHASE}
export END_PHASE=${END_PHASE:-$DEFAULT_END_PHASE}
export IPOIB_MODES=${IPOIB_MODES:-$DEFAULT_IPOIB_MODES}
export IP1=${IP1:-$DEFAULT_IP1}
export IP2=${IP2:-$DEFAULT_IP2}
export HOST1=
export HOST2=
export DO_MAD=1
export IN_VM=0

source $(dirname $0)/helpers/common.sh
load_helpers $(dirname $0) "common"
load_helpers $(dirname $0) "ib"

usage(){
	echo "Usage: ${0} [options] <host1> <host2>"
	echo "Options:"
	echo "  -h, --help                     Display usage"
	echo "  -s, --start-phase              Phase to start from (default is $DEFAULT_START_PHASE)"
	echo "  -e, --end-phase                Phase to stop at (default is $DEFAULT_END_PHASE)"
	echo "  -p, --phase <#phase>           Launch only this phase"
	echo "  -v, --verbose                  Display test logs in console."
	echo "      --ip1 <ip>                 IP for IPoIB on host1 (default is $DEFAULT_IP1)"
	echo "      --ip2 <ip>                 IP for IPoIB on host2 (default is $DEFAULT_IP2)"
	echo "  -M, --mpi <mpi>[,<mpi>...]     Comma separated list of MPI flavours to test (default is $DEFAULT_MPI_FLAVOURS)"
	echo "  -I, --ipoib <mode>[,<mode>...] Comma separated list of IPoIB mode to test (default is $DEFAULT_IPOIB_MODES)"
	echo "                                 Note that connected mode maybe auto disabled if the HW does not support it"
	echo "  -n, --no-mad                   Disable test that requires MAD support. Needed for testing over SR-IOV"
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
		--ip1)
			IP1=$2
			shift
			;;
		--ip2)
			IP2=$2
			shift
			;;
		-M|--mpi)
			MPI_FLAVOURS=$2
			shift
			;;
		-I|--ipoib)
			IPOIB_MODES=$2
			shift
			;;
		-n|--no-mad)
			DO_MAD=0
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

	juLog -name=h1_kill_opensm "kill_opensm $HOST1"
	juLog -name=h2_kill_opensm "kill_opensm $HOST2"

	if [ $DO_MAD -eq 1 ]; then
		juLog -name=h1_reset_all_ports "reset_all_ports $HOST1"
		juLog -name=h2_reset_all_ports "reset_all_ports $HOST2"

		# We need to sleep a little bit here to let the port reset
		sleep 5
	fi

	juLog -name=h1_firewall_down "firewall_down $HOST1"
	juLog -name=h2_firewall_down "firewall_down $HOST2"

}
run_phase 0 phase_0 "State Cleanup"

set_properties $HOST1
set_properties $HOST2
juLogSetProperty $HOST1.ib_ip $IP1
juLogSetProperty $HOST2.ib_ip $IP2

#########################
#
# Phase 1: Fabric init
# - Start demons (opensm, rdma-ndd)
# - SSH known key setup to as some tests will fail if
#   hosts do not know each other
# - Device status check
#
#########################
phase_1_1(){
	juLog -name=h1_rdma_ndd "setup_rdma_ndd $HOST1"
	juLog -name=h2_rdma_ndd "setup_rdma_ndd $HOST2"

	if [ $DO_MAD -eq 1 ]; then
		juLog_fatal -name=h1_openSM_start "start_opensm $HOST1 -p 10"
		# Leave some time for openSM to bring the link up
		sleep 10
	fi
}
run_phase 1 phase_1_1 "Fabric init (1/2)"

# Do not wrap these as they export needed variables
get_port $HOST1 1
get_port $HOST2 2

phase_1_2(){
	juLog_fatal -name=h1_ip_setup   "set_ipoib_down $HOST1 $IPPORT1; set_ipoib_up $HOST1 $IPPORT1 $IP1/24"
	juLog_fatal -name=h2_ip_setup   "set_ipoib_down $HOST2 $IPPORT2; set_ipoib_up $HOST2 $IPPORT2 $IP2/24"

	# Let IP settle down or SSH key setup might fail
	sleep 5

	juLog_fatal -name=h1_setup_ssh_keys "setup_ssh $HOST1 $IP2"
	juLog_fatal -name=h2_setup_ssh_keys "setup_ssh $HOST2 $IP1"

	juLog_fatal -name=h1_ibvinfo tp $HOST1 ibv_devinfo
	juLog_fatal -name=h2_ibvinfo tp $HOST2 ibv_devinfo

	if [ $DO_MAD -eq 1 ]; then
		juLog_fatal -name=h1_ibdiagnet test_ibdiagnet $HOST1
		juLog_fatal -name=h2_ibdiagnet test_ibdiagnet $HOST2

		juLog -name=h1_test_nodedesc "test_nodedesc $HOST1 $GUID1"
		juLog -name=h2_test_nodedesc "test_nodedesc $HOST2 $GUID2"
	fi
}
run_phase 1 phase_1_2 "Fabric init (2/2)"

#########################
#
# Phase 2: IPoIB
#
#########################
phase_2(){
	local reload_driver=0
	# Check if both cards support connected mode
	if ! (is_connected_supported $HOST1 $IPPORT1 && is_connected_supported $HOST2 $IPPORT2); then
	   #  We are using a mlx5 card with enhanced mode
	   # Test if first then if possible reload the driver  with enhanced mode disabled
	   # so we can testout datagram and connected
		for size in 511 1025 2044 8192 32768 65492; do
			juLog -name=h1_enhanced_ping_$size "test_ping $HOST1 $IP2 $size"
			juLog -name=h2_enhanced_ping_$size "test_ping $HOST2 $IP1 $size"
		done

	   if !(is_enhanced_mode_togglable $HOST1 && is_enhanced_mode_togglable $HOST2); then
		   # No parameter to disable it, do not test out connected/datagram
		   juLog -name=ipoib_skipping_connected 'echo "WARNING: Disabling datagram/connected tests as it is not supported by all HCAs (enhanced mode enabled and not togglable)"'
		   return 0
	   fi
	   reload_driver=1
	   # IPoIB Ifs are reconfigured right after that. No need to to it here
	   juLog -name=h1_disabled_enhanced_kill_opensm "kill_opensm $HOST1"
	   juLog -name=h1_disable_enhanced "disable_enhanced $HOST1"
	   juLog -name=h2_disable_enhanced "disable_enhanced $HOST2"
	   if [ $DO_MAD -eq 1 ]; then
		   juLog -name=h1_disabled_enhanced_start_opensm "start_opensm $HOST1 -p 10"
	   fi
	fi

	for mode in $(echo $IPOIB_MODES | sed -e 's/,/ /g'); do
		juLog_fatal -name=h1_${mode}_ip_mode "set_ipoib_mode $HOST1 $IPPORT1 $mode"
		juLog_fatal -name=h1_${mode}_ip_down "set_ipoib_down $HOST1 $IPPORT1"
		juLog_fatal -name=h1_${mode}_ip_up   "set_ipoib_up $HOST1 $IPPORT1 $IP1/24"

		juLog_fatal -name=h2_${mode}_ip_mode "set_ipoib_mode $HOST2 $IPPORT2 $mode"
		juLog_fatal -name=h2_${mode}_ip_down "set_ipoib_down $HOST2 $IPPORT2"
		juLog_fatal -name=h2_${mode}_ip_up   "set_ipoib_up $HOST2 $IPPORT2 $IP2/24"

		for size in 511 1025 2044 8192 32768 65492; do
			juLog -name=h1_${mode}_ping_$size "test_ping $HOST1 $IP2 $size"
			juLog -name=h2_${mode}_ping_$size "test_ping $HOST2 $IP1 $size"
		done

		# TODO: Add ping tests that are expected to fail

		juLog -name=h1_${mode}_sftp "test_sftp $HOST1 $IP2"
		juLog -name=h1_${mode}_sftp "test_sftp $HOST1 $IP2"
	done
	if [ $reload_driver -eq 1 ]; then
		# Put the driver back in enhanced mode and make sure IPoIB Ifs are reocnfigured
	   juLog -name=h1_enable_enhanced_kill_opensm "kill_opensm $HOST1"
	   juLog -name=h1_enable_enhanced "enable_enhanced $HOST1 && set_ipoib_up $HOST1 $IPPORT1 $IP1/24"
	   juLog -name=h2_enable_enhanced "enable_enhanced $HOST2 && set_ipoib_up $HOST2 $IPPORT2 $IP2/24"
	   if [ $DO_MAD -eq 1 ]; then
		   juLog -name=h1_enabled_enhanced_start_opensm "start_opensm $HOST1 -p 10"
	   fi
	fi
}
run_phase 2 phase_2 "IPoIB"

#########################
#
# Phase 3: SM Failover
#
#########################
phase_3(){
	if [ $DO_MAD -eq 1 ]; then
		juLog -name=test_sm_failover "test_sm_failover $HOST1 $LID1 $HOST2 $LID2"
	fi
}
run_phase 3 phase_3 "SM Failover"

#########################
#
# Phase 4: SRP
#
#########################
phase_4(){
	juLog -name=srp_server test_srp $HOST2 $GUID2 $SYSGUID2 $HCA2 $IBPORT2 $HOST1 $GUID1 $HCA1 $IBPORT1
}
run_phase 4 phase_4 "SRP"

#########################
#
# Phase 5: NFSoRDMA
#
#########################
phase_5(){
	juLog -name=nfs_over_rdma test_nfs $HOST1 $IP1 $HOST2
}
run_phase 5 phase_5 "NFSoRDMA"

#########################
#
# Phase 6: DAPL
#
#########################
phase_6(){
	juLog -name=dapl -error='DAT_' test_dapl $HOST1 $IPPORT1 $HOST2 $IPPORT2 $IP2
}
run_phase 6 phase_6 "DAPL"

#########################
#
# Phase 7: RDMA/Verbs
#
#########################
phase_7(){
	for mode in rc uc ud srq; do
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
	for flavour in $(echo $MPI_FLAVOURS | sed -e 's/,/ /g'); do

		juLog -name=mpitests_${flavour} test_mpi ${flavour} $HOST1 $IP1 $IP2
	done
}
run_phase 8 phase_8 "MPI"

#########################
#
# Phase 9: libfabric
#
#########################
phase_9(){
	juLog -name=fabtests test_libfabric $HOST1 $IP1 $IP2
}
run_phase 9 phase_9 "libfabric"


#########################
#
# Phase 10: NVMEoF
#
#########################
phase_10(){
	juLog -name=nvme test_nvme $HOST2 $IP2 $HOST1
}
run_phase 10 phase_10 "nvme"

