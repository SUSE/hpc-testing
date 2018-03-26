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
