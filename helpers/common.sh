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

#########################
#
# Usefull wrappers
#
#########################
fatal_error()
{
	echo -e "ERROR:" $* >&2
	exit 1
}

ip_addr_show_to_ip()
{
	 grep inet /dev/stdin  | grep -v inet6 | sed -e 's/.*inet \([0-9.]*\)\/\?.*$/\1/'
}
ip_addr_show_to_dev()
{
	local ip=$1
	grep inet /dev/stdin  | grep -v inet6 | grep $ip | awk '{ print $NF}'
}

tp_check_local()
{
	local host=$1
	local varname=IS_LOCAL_$(echo $host | tr '.' '_')

	# Check if the IP is local and store the value
	if [ "${!varname}" == "" ]; then
		export ${varname}=1
		IP_LIST=$(ip addr show | grep inet  | grep -v inet6 | sed -e 's/.*inet \([0-9.]*\)\/\?.*$/\1/')
		for ip in $IP_LIST; do
			if [ "$ip" == "$host" ]; then
				export ${varname}=0
				break
			fi
		done
	fi
	return ${!varname}
}

tp()
{
	local ip=$1
	local host="ssh:$ip"
	shift

	if tp_check_local $ip; then
		echo "$@"
		set -e
		(
			cd $HOME;
			set -x
			eval $@
		)
		set +e
	else
		echo "twopence_command -b $host $@"
		set -e
		twopence_command -t 300 -b $host "set -x; $@"
		set +e
	fi
}

tpq()
{
	local ip=$1
	local host="ssh:$ip"
	local ret=0
	shift

	if tp_check_local $ip; then
		set -e
		(
			cd $HOME;
			eval $@
		)
		ret=$?
		set +e
	else
		set -e
		twopence_command -t 300 -b $host "$@"
		ret=$?
		set +e
	fi
	return $ret
}

load_helpers()
{
	local topdir=$1
	local test_type=$2

	source ${topdir}/helpers/julog.sh
	for helper in $(ls ${topdir}/helpers/${test_type}/[0-9][0-9]* | egrep -v '*~$'); do
		source ${helper}
	done
}

run_phase(){
	local phase=$1
	local func=$2
	shift 2
	juLogSetClassName "phase.$phase.$(echo $* | tr 'A-Z' 'a-z' | tr ' '  '.')"
	if [ $END_PHASE -lt $phase ]; then
		# We reach passed the last phase
		# exit now
		exit 0
	fi
	if [ $START_PHASE -gt $phase -o $END_PHASE -lt $phase ]; then
		echo "Skipping phase $phase"
		return 0
	else
		echo "*******************************"
		echo "*** Phase $phase:" $*
		echo "*******************************"
		eval $func
		status=$?
		echo "*******************************"
		echo "*** End of phase $phase:" $* " Status=$status"
		echo "*******************************"
	fi
}

get_suse_version(){
	local host=$1
	local varname=SUSE_VERSION_$(echo $host | tr '.' '_')

	if [ "${!varname}" == "" ]; then
		export ${varname}=$(tpq $host 'source /etc/os-release; echo $VERSION_ID')
	fi
	echo ${!varname}
	return 0
}

#####################
# Phase parsing stuff
#####################
DEFAULT_START_PHASE=0
DEFAULT_END_PHASE=999

export START_PHASE=${START_PHASE:-$DEFAULT_START_PHASE}
export END_PHASE=${END_PHASE:-$DEFAULT_END_PHASE}
export IN_VM=0
export HOST1=
export HOST2=

common_usage(){
	echo "  -h, --help                     Display usage"
	echo "  -s, --start-phase              Phase to start from (default is $DEFAULT_START_PHASE)"
	echo "  -e, --end-phase                Phase to stop at (default is $DEFAULT_END_PHASE)"
	echo "  -p, --phase <#phase>           Launch only this phase"
	echo "  -v, --verbose                  Display test logs in console."
	echo "      --in-vm                    Test is being run in a virtual machine"

}

common_parse(){
	case $1 in
		-s|--start-phase)
			START_PHASE=$2
			return 2
			;;
		-e|--end-phase)
			END_PHASE=$2
			return 2
			;;
		-p|--phase)
			START_PHASE=$2
			END_PHASE=$2
			return 2
			;;
		-v|--verbose)
			export VERBOSE=1
			return 1
			;;
		--in-vm)
			IN_VM=1
			return 1
			;;
		--help|-h)
			usage $0
			exit 1
			;;
		[0-9]*.[0-9]*.[0-9]*.[0-9]*)
			if [ "$HOST1" == "" ]; then
				HOST1=$1
				return 1
			elif [ "$HOST2" == "" ]; then
				HOST2=$1
				return 1
			else
				fatal_error "Too many host ip provided '$2'"
			fi
			;;
		*)
			return 0
			;;
	esac
}

common_check(){
	if [ "$HOST1" == "" -o "$HOST2" == "" ]; then
		usage $0
		fatal_error "Missing host names"
	fi
}
