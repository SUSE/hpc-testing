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
