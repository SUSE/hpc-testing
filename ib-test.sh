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

DEFAULT_IPOIB_MODES="connected,datagram"

export IPOIB_MODES=${IPOIB_MODES:-$DEFAULT_IPOIB_MODES}
export DO_MAD=1
export KMOD_RELOAD=0
# Unset global variables used later to describe HCA, ports and IPS
export IP1 IP2 IP6_1 IP6_2
export IPPORT1 IPPORT2
export GUID1 GUID2
export LID1 LID2
export HCA1 HCA2
export IBPORT1 IBPORT2
export SYSGUID1 SYSGUID2

source $(dirname $0)/helpers/common.sh
load_helpers $(dirname $0) "common" "ib"

usage(){
    echo "Usage: ${0} [options] <host1> <host2>"
    echo "Options:"
    common_usage
    echo "Interface configuration:"
    echo "      --hca1 <hca name>          Select this specific HCA on host1 (default is first active)"
    echo "      --hca2 <hca name>          Select this specific HCA on host2 (default is first active)"
    echo "      --ip1 <ip>                 IP for IPoIB on host1 (default is current address)"
    echo "      --ip2 <ip>                 IP for IPoIB on host2 (default is current address)"
    echo "      --ip6-1 <ipv6>             IPv6 for IPoIB on host1 (default is current address)"
    echo "      --ip6-2 <ipv6>             IPv6 for IPoIB on host2 (default is current address)"
    echo "Test flags:"
    echo "  -I, --ipoib <mode>[,<mode>...] Comma separated list of IPoIB mode to test (default is $DEFAULT_IPOIB_MODES)"
    echo "                                 Note that connected mode maybe auto disabled if the HW does not support it"
    echo "  -n, --no-mad                   Disable tests that requires MAD support. Needed for testing over SR-IOV"
    echo "  -k, --reload-kmods             Force a full kmod unload/reload. Should only be used when running"
    echo "                                 multiple tests consecutively"
}

while [ $# -ne 0 ]; do
    common_parse $1 $2
    ret=$?
    if [ $ret -ne 0 ]; then
	shift $ret
	continue
    fi

    case $1 in
	--hca1)
	    HCA1=$2
	    shift
	    ;;
	--hca2)
	    HCA2=$2
	    shift
	    ;;
	--ip1)
	    IP1=$2
	    shift
	    ;;
	--ip2)
	    IP2=$2
	    shift
	    ;;
	--ip6-1)
	    IP6_1=$2
	    shift
	    ;;
	--ip6-2)
	    IP6_2=$2
	    shift
	    ;;
	-I|--ipoib)
	    IPOIB_MODES=$2
	    shift
	    ;;
	-n|--no-mad)
	    DO_MAD=0
	    ;;
        -k|--reload-kmods)
            KMOD_RELOAD=1
            ;;
	*)
	    fatal_error "Unknow argument $1"
	    ;;
    esac
    shift
done
common_check

juLogSetProperty host1.name $HOST1
juLogSetProperty host2.name $HOST2
#########################
#
# Phase 0: State cleanup
# - Install required packages
# - Reset everything needed to mimic an after-reboot run
#
#########################
run_phase 0 phase_0 "State Cleanup"

set_properties $HOST1
set_properties $HOST2

#########################
#
# Phase 1-0: Fabric init
# - Start demons (opensm, rdma-ndd)
#
#########################
run_phase 1 phase_1_1 "Fabric init (1/2)"


#########################
#
# Interface setup
# - Find an active HCA if none was requested
# - Extract HCA informations
# - Extract IPv4 and IPv6 addresses if needed
#
#########################
interface_setup

#########################
#
# Phase 1-2: Fabric init
# - SSH known key setup to as some tests will fail if
#   hosts do not know each other
# - Device status check
#
#########################
run_phase 1 phase_1_2 "Fabric init (2/2)"

#########################
#
# Phase 2: IPoIB
#
#########################
run_phase 2 ipoib_run_tests "IPoIB"

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
    rdma_perf  $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2
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

