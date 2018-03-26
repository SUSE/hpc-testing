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
