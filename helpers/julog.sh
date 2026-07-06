### Copyright 2010 Manuel Carrasco Moñino. (manolo at apache.org)
### Copyright 2016 Patrick Double (pat at patdouble.com)
###
### Licensed under the Apache License, Version 2.0.
### You may obtain a copy of it at
### http://www.apache.org/licenses/LICENSE-2.0

###
### A library for shell scripts which creates reports in jUnit format.
### These reports can be used in Hudson, or any other CI.
###
### Usage:
###     - source this file in your shell script
###     - Use juLog to call your command any time you want to produce a new report
###        Usage:   juLog <options> command arguments
###           options:
###             -name="TestName" : the test name which will be shown in the junit report
###             -error="RegExp"  : a regexp which sets the test as failure when the output matches it
###             -ierror="RegExp" : same as -error but case insensitive
###     - Junit reports are left in the folder 'result' under the directory where the script is executed.
###     - Configure hudson to parse junit files from the generated folder
###

juASSERTS=00; juERRORS=0; juTOTALTIME=0; juCONTENT=""
juERRORED_TESTS=""
juPROPERTIES=""
juCLASSNAME="default"
juTIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%S')

# create output folder
juDIR=${CIRCLE_TEST_REPORTS:-`pwd`/results}
mkdir -p "$juDIR" || exit

# The name of the suite is calculated based in your script name
juSUITE=`basename $0 2> /dev/null | sed -e 's/.sh$//' | tr "." "_"`

# A wrapper for the eval method which allows catching seg-faults and use tee
juERRFILE=/tmp/evErr.$$.log

eVal() {
  (eval "$1")
  echo $? | tr -d "\n" >$juERRFILE
}

juLogRefreshFile() {
  ## testsuite block
  cat <<EOF > "$juDIR/TEST-$juSUITE.xml"
  <testsuite failures="0" name="$juSUITE" tests="$juASSERTS" errors="$juERRORS" time="$juTOTALTIME" hostname="$(hostname)" timestamp="$juTIMESTAMP">
    <properties>$juPROPERTIES
    </properties>
    $juCONTENT
  </testsuite>
EOF
}

juLogSetProperty() {
	juPROPERTIES="$juPROPERTIES
        <property name=\"$1\" value=\"$2\" />"
	juLogRefreshFile
}

juLogSetClassName() {
	juCLASSNAME="$1"
}

# Method to clean old tests
juLogClean() {
  echo "+++ Removing old junit reports from: $juDIR "
  rm -f "$juDIR"/TEST-*
}

# Execute a command and record its results
juLog() {

  # parse arguments
  local ya="" icase="" raw_name="" name="" ereg="" cmd=""
  while [ -z "$ya" ]; do
    case "$1" in
      -name=*)   raw_name=`echo "$1" | sed -e 's/-name=//'`; name=$juASSERTS-$raw_name;   shift;;
      -ierror=*) ereg=`echo "$1" | sed -e 's/-ierror=//'`; icase="-i"; shift;;
      -error=*)  ereg=`echo "$1" | sed -e 's/-error=//'`;  shift;;
      *)         ya=1;;
    esac
  done

  # use first arg as name if it was not given
  if [ -z "$name" ]; then
    raw_name=$1
    name="$juASSERTS-$raw_name"
  fi

  # calculate command to eval
  [ -z "$1" ] && return
  cmd="$1"; shift
  while [ -n "$1" ]
  do
     cmd="$cmd \"$1\""
     shift
  done

  if type is_test_skipped &>/dev/null && { is_test_skipped "$raw_name" || is_test_skipped "$name"; }; then
      echo "[SKIPPED][$juSUITE][$name] Test skipped by CLI option"
      juASSERTS=`expr $juASSERTS + 1`
      juASSERTS=`printf "%.2d" $juASSERTS`
      juCONTENT="$juCONTENT
    <testcase name=\"$name\" time=\"0\" classname=\"$juCLASSNAME\">
        <skipped message=\"test skipped by CLI option\" />
    </testcase>
  "
      juLogRefreshFile
      return 0
  fi

  # eval the command sending output to a file
  outf=/var/tmp/ju$$.txt
  >$outf
  echo ""                         | tee -a $outf
  echo "[RUNNING][$juSUITE][$name] $cmd" | tee -a $outf
  ini=`date +%s.%N`
  if [ "$VERBOSE" != "" ]; then
	  eVal "$cmd" 2>&1 | tee -a $outf
  else
	  eVal "$cmd" >> $outf 2>&1
  fi
  evErr=`cat $juERRFILE`
  rm -f $juERRFILE
  end=`date +%s.%N`
  echo "+++ exit code: $evErr"    | tee -a $outf

  # set the appropriate error, based in the exit code and the regex
  [ $evErr != 0 ] && err=1 || err=0
  out=`cat $outf | sed -e 's/^\([^+]\)/| \1/g'`
  if [ $err = 0 -a -n "$ereg" ]; then
      H=`echo "$out" | egrep $icase "$ereg"`
      [ -n "$H" ] && err=1
  fi
  rm -f $outf

  # calculate vars
  juASSERTS=`expr $juASSERTS + 1`
  juASSERTS=`printf "%.2d" $juASSERTS`
  juERRORS=`expr $juERRORS + $err`
  time=`echo $end - $ini | bc`
  juTOTALTIME=`echo $juTOTALTIME + $time | bc`

  # write the junit xml report
  ## failure tag
  if [ $err = 0 ]; then
      failure=""
  else
      failure="<failure type=\"ScriptError\" message=\"$name failed\"></failure>"
      juERRORED_TESTS="${juERRORED_TESTS} - $name\n"
  fi
  tcerr=""
  if [ -n "$failure" ]; then
  	tcerr="juERRORS=\"1\""
  fi
  ## testcase tag
  juCONTENT="$juCONTENT
    <testcase name=\"$name\" $tcerr time=\"$time\" classname=\"$juCLASSNAME\">
        $failure
        <system-out>
<![CDATA[
$out
]]>
        </system-out>
    </testcase>
  "
  ## testsuite block
  juLogRefreshFile

  return $evErr
}
juLog_summary()
{
	if [ $? -eq 0 -a $juERRORS -eq 0 ]; then
		echo "[SUCCESS][$juSUITE] Testsuite summary: tests=$juASSERTS errors=$juERRORS time=$juTOTALTIME"
		exit 0
	else
		echo "[FAILURE][$juSUITE] Testsuite summary: tests=$juASSERTS errors=$juERRORS time=$juTOTALTIME"
		echo "List of failed tests:"
		echo -en $juERRORED_TESTS
		exit 1
	fi
}
trap juLog_summary EXIT

juLog_fatal() {
	juLog "$@"
	if [ $? -ne 0 ]; then
		echo "[ERROR][$juSUITE] Fatal failure. Exiting..." >&2
		exit 1
	fi
}
