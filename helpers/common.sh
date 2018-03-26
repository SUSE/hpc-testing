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
			eval $@
		)
		set +e
	else
		echo "twopence_command -b $host $@"
		set -e
		twopence_command -b $host "$@"
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
		twopence_command -b $host "$@"
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
	if [ $START_PHASE -gt $phase -o $END_PHASE -lt $phase ]; then
		echo "Skipping phase $phase"
		return 0
	else
		echo "*******************************"
		echo "*** Phase $phase:" $*
		echo "*******************************"
		eval $func
		if [ $? -ne 0 ]; then
			fatal_error "Phase failed"
		fi
	fi
}
