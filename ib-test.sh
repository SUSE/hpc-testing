#!/bin/bash

source $(dirname $0)/julog.sh

if [ $# -ne 2 ]; then
	fatal_error "Usage $0 host1 host2" >&2
fi
export HOST1=$1
export HOST2=$2

source $(dirname $0)/common-helpers.sh
source $(dirname $0)/ib-test-helpers.sh

#########################
#
# Phase 0: State cleanup
# - Install required packages
# - Reset everything needed to mimic an after-reboot run
#
#########################
juLog_fatal -name=h1_setup_requirements "setup_requirements $HOST1"
juLog_fatal -name=h2_setup_requirements "setup_requirements $HOST2"

juLog -name=h1_kill_opensm "kill_opensm $HOST1"
juLog -name=h2_kill_opensm "kill_opensm $HOST2"

juLog -name=h1_reset_all_ports "reset_all_ports $HOST1"
juLog -name=h2_reset_all_ports "reset_all_ports $HOST2"

#########################
#
# Phase 1: Fabric init
# - Start demons (opensm, rdma-ndd)
# - SSH known key setup to as some tests will fail if
#   hosts do not know each other
# - Device status check
#
#########################
juLog -name=h1_rdma_ndd "setup_rdma_ndd $HOST1"
juLog -name=h2_rdma_ndd "setup_rdma_ndd $HOST2)"

# We need to sleep a little bit here in case the port are stil reseting from pahse 0
sleep 1
juLog_fatal -name=h1_openSM_start "start_opensm $HOST1"

# Do not wrap these as they export needed variables
get_port $HOST1 1
get_port $HOST2 2

IP1=192.168.0.1
IP2=192.168.0.2

juLog_fatal -name=h1_setup_ssh_keys "setup_ssh $HOST1 $IP2"
juLog_fatal -name=h2_setup_ssh_keys "setup_ssh $HOST2 $IP1"

juLog_fatal -name=h1_ibvinfo tp $HOST1 ibv_devinfo
juLog_fatal -name=h2_ibvinfo tp $HOST2 ibv_devinfo

juLog_fatal -name=h1_ibdiagnet test_ibdiagnet $HOST1
juLog_fatal -name=h2_ibdiagnet test_ibdiagnet $HOST2

juLog -name=h1_test_nodedesc "test_nodedesc $HOST1 $GUID1"
juLog -name=h2_test_nodedesc "test_nodedesc $HOST2 $GUID2)"

#########################
#
# Phase 2: IPoIB
#
#########################

#
# Connected mode
#
juLog_fatal -name=h1_cm_ip_mode "set_ipoib_mode $HOST1 $IPPORT1 connected"
juLog_fatal -name=h1_cm_ip_down "set_ipoib_down $HOST1 $IPPORT1"
juLog_fatal -name=h1_cm_ip_up   "set_ipoib_up $HOST1 $IPPORT1 $IP1/24"

juLog_fatal -name=h2_cm_ip_mode "set_ipoib_mode $HOST2 $IPPORT2 connected"
juLog_fatal -name=h2_cm_ip_down "set_ipoib_down $HOST2 $IPPORT2"
juLog_fatal -name=h2_cm_ip_up   "set_ipoib_up $HOST2 $IPPORT2 $IP2/24"

for size in 511 1025 2044 8192 32768 65492; do
	juLog -name=h1_cm_ping_$size "test_ping $HOST1 $IP2 $SIZE"
	juLog -name=h2_cm_ping_$size "test_ping $HOST2 $IP1 $SIZE"
done

# TODO: Add ping tests that are expected to fail

juLog -name=h1_cm_sftp "test_sftp $HOST1 $IP2"
juLog -name=h1_cm_sftp "test_sftp $HOST1 $IP2"

#
# Datagram mode
#
juLog_fatal -name=h1_ud_ip_mode "set_ipoib_mode $HOST1 $IPPORT1 datagram"
juLog_fatal -name=h1_ud_ip_down "set_ipoib_down $HOST1 $IPPORT1"
juLog_fatal -name=h1_ud_ip_up   "set_ipoib_up $HOST1 $IPPORT1 $IP1/24"

juLog_fatal -name=h2_ud_ip_mode "set_ipoib_mode $HOST2 $IPPORT2 datagram"
juLog_fatal -name=h2_ud_ip_down "set_ipoib_down $HOST2 $IPPORT2"
juLog_fatal -name=h2_ud_ip_up   "set_ipoib_up $HOST2 $IPPORT2 $IP2/24"

for size in 511 1025 2044 8192 32768 65492; do
	juLog -name=h1_ud_ping_$size "test_ping $HOST1 $IP2 $SIZE"
	juLog -name=h2_ud_ping_$size "test_ping $HOST2 $IP1 $SIZE"
done

# TODO: Add ping tests that are expected to fail

juLog -name=h1_ud_sftp "test_sftp $HOST1 $IP2"
juLog -name=h1_ud_sftp "test_sftp $HOST1 $IP2"

#########################
#
# Phase 3: SM Failover
#
#########################

#########################
#
# Phase 4: SRP
#
#########################
juLog -name=ibsrpdm tp $HOST1 '/usr/sbin/ibsrpdm'

#########################
#
# Phase 5: NFSoRDMA
#
#########################
juLog -name=nfs_over_rdma test_nfs $HOST1 $IP1 $HOST2

#########################
#
# Phase 6: DAPL
#
#########################

#########################
#
# Phase 7: RDMA/Verbs
#
#########################

juLog -name=rc_pingpong "(
	  test_ibv_pingpong ibv_rc_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2 &&
	  test_ibv_pingpong ibv_rc_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
)"
juLog -name=uc_pingpong "(
	  test_ibv_pingpong ibv_uc_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2 &&
	  test_ibv_pingpong ibv_uc_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
)"
juLog -name=ud_pingpong "(
	  test_ibv_pingpong ibv_ud_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2 &&
	  test_ibv_pingpong ibv_ud_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
)"
juLog -name=srq_pingpong "(
	  test_ibv_pingpong ibv_srq_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2 &&
	  test_ibv_pingpong ibv_srq_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
)"
#########################
#
# Phase 8: MPI
#
#########################
juLog -name=mpitests_mvapich2 test_mpi mvapich2 $HOST1 $IP1 $IP2
juLog -name=mpitests_mpich    test_mpi mpich    $HOST1 $IP1 $IP2
juLog -name=mpitests_openmpi  test_mpi openmpi  $HOST1 $IP1 $IP2
juLog -name=mpitests_openmpi2 test_mpi openmpi2 $HOST1 $IP1 $IP2

#########################
#
# Phase 9: libfabric
#
#########################
juLog -name=fabtests test_libfabric $HOST1 $IP1 $IP2

