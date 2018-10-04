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
	shift

	if tp_check_local $ip; then
		set -e
		(
			cd $HOME;
			eval $@
		)
		set +e
	else
		set -e
		twopence_command -t 300 -b $host "$@"
		set +e
	fi
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
