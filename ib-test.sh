#!/bin/bash

source $(dirname $0)/julog.sh

if [ $# -ne 2 ]; then
	fatal_error "Usage $0 host1 host2" >&2
fi
export HOST1=$1
export HOST2=$2

#
# Usefull wrappers
#
fatal_error()
{
	echo -e "ERROR:" $* >&2
	exit 1
}

tp()
{
	local host="ssh:$1"
	shift
	echo "twopence_command -b $host $@"
	set -e
	twopence_command -b $host "$@"
	set +e
}
tpq()
{
	local host="ssh:$1"
	shift
	set -e
	twopence_command -b $host "$@"
	set +e
}



#
# Test functions
#
setup_requirements()
{
	local host=$1
	echo "Setting up needed packages on $host"
	tp $host "zypper install --no-confirm opensm infiniband-diags rdma-ndd libibverbs-utils srp_daemon fabtests mpitests-mvapich2"
}

setup_rdma_ndd()
{
	local host=$1
	tp $host 'systemctl status rdma-ndd ||
	   		  (systemctl start rdma-ndd && systemctl status rdma-ndd)'
}

reset_all_ports()
{
	local host=$1

	tp $host "for port_id in \$(seq 1 \$(ibstat -p | wc -l)); do
	   		 	   ibportstate -D 0 \$port_id reset;
			   done"
}

get_port()
{
	local host=$1
	local host_id=$2

	local boards=$(tpq $host '/usr/sbin/ibstat -l')
	local ip_count=0
	for board in $boards; do
		local port_count=$(tpq $host "/usr/sbin/ibstat $board -p" | wc -l)
		for port in $(seq 1 $port_count); do
			res=$(tpq $host "/usr/sbin/ibstat $board $port")
			status=$(echo "$res" | grep "State:" | awk '{print $NF}')
			if [ "$status" == "Active" ]; then
				guid=$(echo "$res" | grep "Port GUID:" | awk '{print $NF}')
				lid=$(echo "$res" | grep "Base lid:" | awk '{print $NF}')
				echo "[SUCCESS] Host $host uses interface ib$ip_count."\
					 " Board=$board Port=$port GUID=$guid LID=$lid"
				eval export IPPORT$host_id=ib$ip_count
				eval export GUID$host_id=$guid
				eval export LID$host_id=$lid
				eval export HCA$host_id=$board
				eval export IBPORT$host_id=$port

				return
			fi
			ip_count=$(expr $ip_count + 1)
		done
	done
	fatal_error "Failed to find an active port on $host"
}

set_ip()
{
	local host=$1
	local port=$2
	local ipaddr=$3 #ip/netmask

	tp $host "ip link set dev $port down &&
	   		  ip addr flush $port &&
			  ip link set dev $port up &&
			  ip addr add $ipaddr dev $port"
}

test_ping()
{
	local host=$1
	local remote_addr=$2

	tp $host "ping -c 1 -t 1 $remote_addr"
}

# Check bsc#972725
test_nodedesc()
{
	local host=$1
	local guid=$2

	node_desc=$(tpq $host "smpquery -G NodeDesc $guid" | \
					sed -e 's/^Node Description:\.*//' | awk '{ print $1}')
	rhostname=$(tpq $host "hostname -s")
	if [ "$node_desc" != "$rhostname" ]; then
		fatal_error "Missing or bad hostname in node description" >&2
	fi
}

test_ibv_pingpong()
{
	local testname=$1

	local host1=$2
	local hca1=$3
	local ibport1=$4

	local host2=$5
	local hca2=$6
	local ibport2=$7

	tp $host2 "$testname -d $hca2 -i $ibport2" &
	sleep 1
	tp $host1 "$testname -d $hca1 -i $ibport1 $host2"

	wait
}

test_nfs()
{
	local server=$1
	local server_ip=$2
	local client=$3

	tp $client "! (mount | grep /tmp/RAM) || umount -f /tmp/RAM"

	tp $server "exportfs -u -a &&
	   		   systemctl stop nfs-server &&
			   (! (mount | grep /tmp/RAM) || umount -f /tmp/RAM) &&
			   mkdir -p /tmp/RAM && mount -t tmpfs -o size=2G tmpfs /tmp/RAM &&
			   echo '/tmp/RAM   192.168.0.0/255.255.255.0(fsid=0,rw,async,insecure,no_root_squash)'> /etc/exports &&
			   systemctl start nfs-server &&
			   modprobe svcrdma &&
			   echo 'rdma 20049' > /proc/fs/nfsd/portlist &&
	   		   exportfs -a &&
			   dd if=/dev/urandom bs=1M count=64 of=/tmp/RAM/input"

	tp $client "modprobe xprtrdma &&
	   		   mkdir -p /tmp/RAM &&
			   mount -o rdma,port=20049 $server_ip:/tmp/RAM /tmp/RAM &&
			   (cat /proc/mounts | grep /tmp/RAM  | grep proto=rdma) &&
			   dd if=/tmp/RAM/input bs=1M count=1024 of=/tmp/RAM/output &&
			   diff -q /tmp/RAM/input /tmp/RAM/output"
	tp $server "diff -q /tmp/RAM/input /tmp/RAM/output"

	# Cleanup
	tp $client "umount -f /tmp/RAM"
	tp $server "exportfs -u -a &&
	   		   systemctl stop nfs-server &&
			   umount -f /tmp/RAM &&
			   echo > /etc/exports"
}

test_libfabric()
{
	local host=$1
	local server_ip=$2
	local client_ip=$3
	# Ignore fi_rdm_shared_av which is broken upstream
	tp $host -t 300 "/usr/bin/runfabtests.sh -e fi_rma_bw -v  verbs $server_ip $client_ip"
}

setup_ssh()
{
	local host=$1
	local remote_ip=$2

	# Make sure we accepted the remote SSH key so MPI can work
	tp $host "touch .ssh/known_hosts &&
	   		  sed -i '/^$remote_ip /d' .ssh/known_hosts &&
			  ssh-keyscan $remote_ip >> .ssh/known_hosts"
}

test_mpi()
{
	local flavor=$1
	local host=$2
	local ip1=$3
	local ip2=$4

	export RUN_ARGS="--host 192.168.0.1,192.168.0.2 -np 2"
	tp $host -t 300 "VERBOSE=1 RUN_ARGS='--host $ip1,$ip2 -np 2' SHORT=1 /usr/lib64/mpi/gcc/$flavor/tests/runtests.sh"
}

juLog_fatal -name=setup_requirements "( setup_requirements $HOST1 && setup_requirements $HOST2)"
juLog -name=kill_opensm "(
	  tp $HOST1 'killall opensm; sleep 1; killall -9 opensm || true';
	  tp $HOST2 'killall opensm; sleep 1; killall -9 opensm || true'
 )"

juLog -name=reset_all_ports "(reset_all_ports $HOST1 && reset_all_ports $HOST2)"

juLog -name=rdma_ndd "(setup_rdma_ndd $HOST1 && setup_rdma_ndd $HOST2)"

sleep 1
juLog_fatal -name=openSM_start tp $HOST1 'opensm --daemon'

# Do not wrap these as they export needed variables
get_port $HOST1 1
get_port $HOST2 2

IP1=192.168.0.1
IP2=192.168.0.2

juLog_fatal -name=set_ip "(set_ip $HOST1 $IPPORT1 $IP1/24 && set_ip $HOST2 $IPPORT2 $IP2/24)"
juLog_fatal -name=setup_ssh_keys "(setup_ssh $HOST1 $IP2 && setup_ssh $HOST2 $IP1)"

juLog_fatal -name=host1_ibvinfo tp $HOST1 ibv_devinfo
juLog_fatal -name=host2_ibvinfo tp $HOST2 ibv_devinfo

juLog -name=test_ping "(test_ping $HOST1 $IP2 && test_ping $HOST2 $IP1)"
juLog -name=test_nodedesc "(test_nodedesc $HOST1 $GUID1 && test_nodedesc $HOST2 $GUID2)"

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

juLog -name=nfs_over_rdma test_nfs $HOST1 $IP1 $HOST2
juLog -name=ibsrpdm tp $HOST1 '/usr/sbin/ibsrpdm'
juLog -name=fabtests test_libfabric $HOST1 $IP1 $IP2
juLog -name=mpitests_mvapich2 test_mpi mvapich2 $HOST1 $IP1 $IP2
