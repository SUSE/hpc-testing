#!/bin/bash

#
# Usefull wrappers
#
fatal_error()
{
	echo -e "ERROR:" $* >&2
	exit 1
}

quiet_tp()
{
	local host="ssh:$1"
	shift
	log=$(twopence_command -b $host "$@" 2>&1)
	if [ $? -ne 0 ]; then
		fatal_error "Command twopence_command -b $host $@ failed:\n$log"
	fi
}

tp()
{
	local host="ssh:$1"
	shift
	set -e
	twopence_command -b $host "$@"
	set +e
}
tp_canfail()
{
	local host="ssh:$1"
	shift
	twopence_command -b $host "$@"
}


#
# JUnit helpers
#
add_skipped_test(){
    local destdir=$1
    local component=$2
    local targname=$3
    local errmsg=$4
    local exec_time=$5

    skipped=`cat $destdir/JUnit/nb.skipped`;
    echo `expr $skipped + 1` > $destdir/JUnit/nb.skipped;
    echo -e "\t<testcase classname=\"$component\" name=\"$targname\" time=\"$exec_time\" >" >> $destdir/JUnit/tests.xml;
    echo -e "\t\t<skipped message=\"Skipped\" >\n<![CDATA[" >> $destdir/JUnit/tests.xml;
    echo $errmsg  >> $destdir/JUnit/tests.xml;
    echo -e "]]>\n\t\t</skipped>\n\t</testcase>" >> $destdir/JUnit/tests.xml

}

add_error_test(){
    local destdir=$1
    local component=$2
    local targname=$3
    local exec_time=$4

    errors=`cat $destdir/JUnit/nb.errors`;
    echo `expr $errors + 1` > $destdir/JUnit/nb.errors;
    echo -e "\t<testcase classname=\"$component\" name=\"$targname\" time=\"$exec_time\" >" >> $destdir/JUnit/tests.xml;
    echo -e "\t\t<failure type=\"Error\" >\n<![CDATA[" >> $destdir/JUnit/tests.xml;
    cat $destdir/JUnit/make.log  >> $destdir/JUnit/tests.xml;
    echo -e "]]>\n\t\t</failure>\n\t</testcase>" >> $destdir/JUnit/tests.xml
}

add_succesfull_test(){
    local destdir=$1
    local component=$2
    local targname=$3
    local exec_time=$4

    echo -e "\t<testcase classname=\"$component\" name=\"$targname\" time=\"$exec_time\" >" >> $destdir/JUnit/tests.xml;
    echo -e "\t\t<system-out>\n<![CDATA[" >> $destdir/JUnit/tests.xml;
    cat $destdir/JUnit/make.log  >> $destdir/JUnit/tests.xml;
    echo -e "]]>\n\t\t</system-out>\n\t</testcase>" >> $destdir/JUnit/tests.xml

}
post_target(){
    local destdir=$1;
        local targfile=$destdir/JUnit/results.xml
    echo -e "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n"\
                "<testsuite errors=\"0\" skipped=\"$(cat $destdir/JUnit/nb.skipped)\" failures=\"$(cat $destdir/JUnit/nb.errors)\" time=\"$(cat $destdir/JUnit/exec.time)\" tests=\"$(cat $destdir/JUnit/nb.total)\"  name=\"$(basename $destdir | sed -e 's/\./_/g')\" hostname=\"$(hostname)\">\n"\
                "       <properties>\n" \
         "              <property value=\"$(hostname)\" name=\"host.name\"/>\n"\
                "               <property value=\"$(uname -p)\" name=\"host.kernel.arch\"/>\n"\
                "               <property value=\"$(uname -r)\" name=\"host.kernel.release\"/>\n"\
                "       </properties>\n"   > ${targfile}
         cat $destdir/JUnit/tests.xml >> ${targfile}
         echo -e "\n</testsuite>\n" >> ${targfile}

}

setup_requirements()
{
	local host=$1
	echo "Setting up needed packages on $host"
	quiet_tp $host "zypper install --no-confirm opensm infiniband-diags rdma-ndd libibverbs-utils"
}

setup_rdma_ndd()
{
	local host=$1
	quiet_tp $host 'systemctl status rdma-ndd || (systemctl start rdma-ndd && systemctl status rdma-ndd)'
}

reset_all_ports()
{
	local host=$1

	quiet_tp $host "for port_id in \$(seq 1 \$(ibstat -p | wc -l)); do ibportstate -D 0 \$port_id reset > /dev/null; done"
}

get_port()
{
	local host=$1
	local host_id=$2

	local boards=$(tp $host '/usr/sbin/ibstat -l')
	local ip_count=0
	for board in $boards; do
		local port_count=$(tp $host "/usr/sbin/ibstat $board -p" | wc -l)
		for port in $(seq 1 $port_count); do
			res=$(tp $host "/usr/sbin/ibstat $board $port")
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

	quiet_tp $host "ip link set dev $port down"
	quiet_tp $host "ip addr flush $port"
	quiet_tp $host "ip link set dev $port up"
	quiet_tp $host "ip addr add $ipaddr dev $port"
}

test_ping()
{
	local host=$1
	local remote_addr=$2

	quiet_tp $host "ping -c 1 -t 1 $remote_addr" > /dev/null
	echo "[SUCCESS] Pinged $remote_addr from $host"
}

# Check bsc#972725
test_nodedesc()
{
	local host=$1
	local guid=$2

	node_desc=$(tp $host "smpquery -G NodeDesc $guid" | \
					sed -e 's/^Node Description:\.*//' | awk '{ print $1}')
	rhostname=$(tp $host "hostname -s")
	if [ "$node_desc" != "$rhostname" ]; then
		fatal_error "Missing or bad hostname in node description" >&2
	else
		echo "[SUCCESS] Node Description of $host is OK"
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

	quiet_tp $host2 "$testname -d $hca2 -i $ibport2" &
	sleep 1
	quiet_tp $host1 "$testname -d $hca1 -i $ibport1 $host2"

	wait
	echo "[SUCCESS] $testname $host1 => $host2"
}

test_nfs()
{
	local server=$1
	local server_ip=$2
	local client=$3

	quiet_tp $client "! (mount | grep /tmp/RAM) || umount -f /tmp/RAM"

	quiet_tp $server "exportfs -u -a"
	quiet_tp $server "systemctl stop nfs-server"
	quiet_tp $server "! (mount | grep /tmp/RAM) || umount -f /tmp/RAM"
	quiet_tp $server "mkdir -p /tmp/RAM && mount -t tmpfs -o size=2G tmpfs /tmp/RAM"
	quiet_tp $server "echo '/tmp/RAM   192.168.0.0/255.255.255.0(fsid=0,rw,async,insecure,no_root_squash)'> /etc/exports"
	quiet_tp $server "systemctl start nfs-server"
	quiet_tp $server "modprobe svcrdma"
	quiet_tp $server "echo 'rdma 20049' > /proc/fs/nfsd/portlist"
	quiet_tp $server "exportfs -a"

	quiet_tp $server "dd if=/dev/urandom bs=1M count=64 of=/tmp/RAM/input"

	quiet_tp $client "modprobe xprtrdma"
	quiet_tp $client "mkdir -p /tmp/RAM"
	quiet_tp $client "mount -o rdma,port=20049 $server_ip:/tmp/RAM /tmp/RAM"
	quiet_tp $client "cat /proc/mounts | grep /tmp/RAM  | grep proto=rdma"
	quiet_tp $client "dd if=/tmp/RAM/input bs=1M count=1024 of=/tmp/RAM/output"

	quiet_tp $client "diff -q /tmp/RAM/input /tmp/RAM/output"
	quiet_tp $server "diff -q /tmp/RAM/input /tmp/RAM/output"

	# Cleanup
	quiet_tp $client "umount -f /tmp/RAM"
	quiet_tp $server "exportfs -u -a"
	quiet_tp $server "systemctl stop nfs-server"
	quiet_tp $server "umount -f /tmp/RAM"
	quiet_tp $server "echo > /etc/exports"
	echo "[SUCCESS] NFS over RDMA is working"
}

setup_ssh()
{
	local host=$1
	local remote_ip=$2

	# Make sure we accepted the remote SSH key so MPI can work
	quiet_tp $host "sed -i '/^$remote_ip /d' ~/.ssh/know_hosts && ssh-keyscan $remote_ip >> .ssh/know_hosts"
}

if [ $# -ne 2 ]; then
	fatal_error "Usage $0 host1 host2" >&2
fi
HOST1=$1
HOST2=$2

setup_requirements $HOST1
setup_requirements $HOST2
echo "[SUCCESS] Requirements installed"

quiet_tp $HOST1 'killall opensm; sleep 1; killall -9 opensm || true'
quiet_tp $HOST2 'killall opensm; sleep 1; killall -9 opensm || true'
echo "[SUCCESS] Installed and killed existing openSM"

reset_all_ports $HOST1
reset_all_ports $HOST2
echo "[SUCCESS] Reset all IB ports"

setup_rdma_ndd $HOST1
setup_rdma_ndd $HOST2
echo "[SUCCESS] rdma-ndd setup"

sleep 1
quiet_tp $HOST1 'opensm --daemon'
echo "[SUCCESS] OpenSM started"

get_port $HOST1 1
get_port $HOST2 2

IP1=192.168.0.1
IP2=192.168.0.2

set_ip $HOST1 $IPPORT1 $IP1/24
set_ip $HOST2 $IPPORT2 $IP2/24
echo "[SUCCESS] IP setup"

# test_ping $HOST1 $IP2
# test_ping $HOST2 $IP1

# test_nodedesc $HOST1 $GUID1
# test_nodedesc $HOST2 $GUID2

# test_ibv_pingpong ibv_rc_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2
# test_ibv_pingpong ibv_rc_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
# test_ibv_pingpong ibv_uc_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2
# test_ibv_pingpong ibv_uc_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
# test_ibv_pingpong ibv_ud_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2
# test_ibv_pingpong ibv_ud_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1
# test_ibv_pingpong ibv_srq_pingpong $HOST1 $HCA1 $IBPORT1 $HOST2 $HCA2 $IBPORT2
# test_ibv_pingpong ibv_srq_pingpong $HOST2 $HCA2 $IBPORT2 $HOST1 $HCA1 $IBPORT1

test_nfs $HOST1 $IP1 $HOST2

setup_ssh $HOST1 $IP2
setup_ssh $HOST2 $IP1
