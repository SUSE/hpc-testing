
#########################
#
# Test functions for phase 0
#
#########################
setup_requirements()
{
	local host=$1
	echo "Setting up needed packages on $host"
	tp $host "zypper install --no-confirm opensm infiniband-diags rdma-ndd libibverbs-utils srp_daemon fabtests mpitests-mvapich2 mpitests-openmpi mpitests-openmpi2 mpitests-mpich ibutils "
}

kill_opensm()
{
	local host=$1
	tp $host 'killall opensm; sleep 1; killall -9 opensm || true';
}
reset_all_ports()
{
	local host=$1

	tp $host "for port_id in \$(seq 1 \$(ibstat -p | wc -l)); do
	   		 	   ibportstate -D 0 \$port_id reset;
			   done"
}

#########################
#
# Test functions for phase 1
#
#########################
setup_rdma_ndd()
{
	local host=$1
	tp $host 'systemctl status rdma-ndd ||
	   		  (systemctl start rdma-ndd && systemctl status rdma-ndd)'
}

start_opensm()
{
	local host=$1
	tp $host "opensm --daemon"
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

setup_ssh()
{
	local host=$1
	local remote_ip=$2

	# Make sure we accepted the remote SSH key so MPI can work
	tp $host "touch .ssh/known_hosts &&
	   		  sed -i '/^$remote_ip /d' .ssh/known_hosts &&
			  ssh-keyscan $remote_ip >> .ssh/known_hosts"
}

test_ibdiagnet()
{
	local host=$1
	tp $HOST1 rm -f topo.out
	tp $HOST1 ibdiagnet -wt topo.out
	tp $HOST1 ibdiagnet -pc
	sleep 17
	tp $HOST1 ibdiagnet -c 1000

#   We should check the against the topo file
#   But I cannot figure out how to know which of the system name is ours
#	tp $HOST1 ibdiagnet -t topo2.out
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

#########################
#
# Test functions for phase 2
#
#########################
set_ipoib_mode()
{
	local host=$1
	local port=$2
	local mode=$3

	tp $host "echo $mode > /sys/class/net/$port/mode"
	R_MODE=$(tpq $host "cat /sys/class/net/$port/mode")
	if [ "$R_MODE" != "$mode" ]; then
		fatal_error "Failed to set IPoIB mode"
	fi
}
set_ipoib_up()
{
	local host=$1
	local port=$2
	local ipaddr=$3 #ip/netmask

	tp $host "ip link set dev $port up &&
			  ip addr add $ipaddr dev $port"
}
set_ipoib_down()
{
	local host=$1
	local port=$2

	tp $host "ip link set dev $port down &&
	   		  ip addr flush $port"
}

test_ping()
{
	local host=$1
	local remote_addr=$2
	local pkt_size=$3

	tp $host "ip neigh flush $remote_addr"
	tp $host "ping -i 0.2 -t 3 -c 100 -s $pkt_size $remote_addr"
}

test_sftp()
{
	local host=$1
	local remote_addr=$2

	# Generate a random file
	tp $host "rm -f sftp.orig && dd if=/dev/urandom bs=1M count=64 of=sftp.orig"
	# Copy back and forth
	tp $host "scp sftp.orig $remote_addr:sftp.orig && scp $remote_addr:sftp.orig sftp.copy"
	# Check file
	tp $host "diff -q sftp.orig sftp.copy"
}
#########################
#
# Test functions for phase 3
#
#########################

#########################
#
# Test functions for phase 4
#
#########################

#########################
#
# Test functions for phase 5
#
#########################
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

#########################
#
# Test functions for phase 6
#
#########################

#########################
#
# Test functions for phase 7
#
#########################
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

#########################
#
# Test functions for phase 8
#
#########################

test_mpi()
{
	local flavor=$1
	local host=$2
	local ip1=$3
	local ip2=$4

	export RUN_ARGS="--host 192.168.0.1,192.168.0.2 -np 2"
	tp $host -t 300 "VERBOSE=1 RUN_ARGS='--host $ip1,$ip2 -np 2' SHORT=1 /usr/lib64/mpi/gcc/$flavor/tests/runtests.sh"
}

#########################
#
# Test functions for phase 9
#
#########################

test_libfabric()
{
	local host=$1
	local server_ip=$2
	local client_ip=$3
	# Ignore fi_rdm_shared_av which is broken upstream
	tp $host -t 300 "/usr/bin/runfabtests.sh -e fi_rma_bw -v  verbs $server_ip $client_ip"
}

