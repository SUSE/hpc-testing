#!/bin/bash

# Small wrapper script use to launch the test suite on internal VM setup
export TESTDIR=$(readlink -f $(dirname $0))
source $TESTDIR/helpers/common.sh
load_helpers $TESTDIR "common"

get_package_list(){
	echo "bash"
}

usage(){
	echo "Usage: ${0} [options] <host1> <host2>"
	common_usage
	echo "  -M, --mpi <mpi>[,<mpi>...]     Comma separated list of MPI flavours to test (default is $DEFAULT_MPI_FLAVOURS)"
}

while [ $# -ne 0 ]; do
	common_parse $1 $2
	ret=$?
	if [ $ret -ne 0 ]; then
		shift $ret
		continue
	fi

	case $1 in
		-M|--mpi)
			MPI_FLAVOURS=$2
			shift
			;;
		*)
			fatal_error "Unknow argument $1"
			;;
	esac
	shift
done
common_check

set_properties $HOST1
set_properties $HOST2

test_ib()
{
	tpq $HOST1 "modprobe mlx5_ib"
	tpq $HOST2 "modprobe mlx5_ib"

	# Wait for IP if to get up
	sleep 3

	IB_IP1=$(tpq $HOST1 "ip addr show ib0" | ip_addr_show_to_ip)
	IB_IP2=$(tpq $HOST2 "ip addr show ib0" | ip_addr_show_to_ip)

	tp $HOST1 "cd $TESTDIR; ./ib-test.sh --no-mad --in-vm --ip1 $IB_IP1 --ip2 $IB_IP2 $HOST1 $HOST2\
   -s $START_PHASE -e $END_PHASE -M $MPI_FLAVOURS"
}

test_rxe()
{
	tpq $HOST1 "rmmod mlx5_ib mlx5_core; true"
	tpq $HOST2 "rmmod mlx5_ib mlx5_core; true"
	tp $HOST1 "cd $TESTDIR; ./rxe-test.sh  --in-vm $HOST1 $HOST2"
}

VERBOSE=1
juLog -name=test_ib test_ib
juLog -name=test_rxe test_rxe
