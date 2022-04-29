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

remove_all_mods_host()
{
	local host=$1
	tpq $host "rmmod rdma_rxe mlx5_ib mlx5_core 2>/dev/null || true"
	check_existing_hw_rdma_if $host
	check_existing_sw_rdma_if $host randomnamethatcannotbeardmainterfacetype
}

remove_all_mods()
{
	remove_all_mods_host $HOST1
	remove_all_mods_host $HOST2
}
test_ib()
{
	remove_all_mods
	tpq $HOST1 "modprobe mlx5_ib"
	tpq $HOST2 "modprobe mlx5_ib"

	# Wait for IP if to get up
	sleep 3

	IB_IF1=$(tpq $HOST1 "ip -br link show type ipoib" | head -n 1 | awk '{print $1}')
	IB_IP1=$(tpq $HOST1 "ip addr show $IB_IF1" | ip_addr_show_to_ip)

	IB_IF2=$(tpq $HOST2 "ip -br link show type ipoib" | head -n 1 | awk '{print $1}')
	IB_IP2=$(tpq $HOST2 "ip addr show $IB_IF2" | ip_addr_show_to_ip)

	tp $HOST1 "cd $TESTDIR; ./ib-test.sh --no-mad --in-vm --ip1 $IB_IP1 --ip2 $IB_IP2 $HOST1 $HOST2 \
   -s $START_PHASE -e $END_PHASE -M $MPI_FLAVOURS"
}

test_rxe()
{
	remove_all_mods
	tpq $HOST1 "modprobe rdma_rxe"
	tpq $HOST2 "modprobe rdma_rxe"
	tp $HOST1 "cd $TESTDIR; ./rxe-test.sh  --in-vm $HOST1 $HOST2"
}

VERBOSE=1
juLog -name=test_ib test_ib
juLog -name=test_rxe test_rxe
