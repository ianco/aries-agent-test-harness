#! /bin/bash

# Configuration Data -- order matters in these arrays. A new entry requires an entry in all "ta_" arrays
ta_tlas=("acapy" "afgo" "javascript" "dotnet")
ta_names=("Aries Cloud Agent Python" "Aries Framework Go" "Aries Framework JavaScript" "Aries Framework .NET")
ta_shortnames=("ACA-Py" "AF-Go" "AFJ" "AF-.NET")
ta_scopes=("AIP 1, 2" "AIP 2" "AIP 1" "AIP 1")
ta_exceptions=("None" "None" "Revocation" "Proof Proposal")
ta_urls=(https://github.com/hyperledger/aries-cloudagent-python \
https://github.com/hyperledger/aries-framework-go \
https://github.com/hyperledger/aries-framework-javascript \
https://github.com/hyperledger/aries-framework-dotnet)
workflows=".github/workflows/test-harness-*"

unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    CYGWIN*)    machine=Cygwin;;
    MINGW*)     machine=MinGw;;
    *)          machine="UNKNOWN:${unameOut}"
esac

usage () {

cat << EOF
Usage: gen-interop.sh [--help]

Generates the Aries Interop tests documentation pages based on the test agents setup and the workflows
defined in the repo. The workflows are in the .github/workflows folder and must be named "test-harness-<name>.yml".

The generator iterates over each workflow file, extracting data from it -- either live
data or from comments. Further, it curl's the related allure "latest" files to get some
data about the last run - tests run, tests passed and date.  All of the data goes into
a set of arrays indexed by the workflow file number.

From there, a README file is created summarizing by Test Agent the run results, and
a file per Test Agent is generated that gives more details about the tests run for that agent.

Basic process:
  Collect all the runset data in arrays
  Generate the header for the summary page (README.md)
  Iterate through the test agents configured in this script.
      Print a summary per test agent showing the results against all other agents.
  Iterate again through the test agents
      Print a details file about about the current test agent (<ta_shortname>.md)
      Print a table listing each runset the test agent is a part of
      Iterate over the runsets
         Print details about each runset the test agent is a part of

To add information about a workflow, insert comments into the YAML with identifiers RUNSET_NAME,
Scope, Summary, and Current.

To exclude a workflow, add a comment "# SKIP", and the process will not include the workflow 
EOF

exit

}

if [ "$1" == "--help" ]; then
    usage
fi

default_value () {
    # Helper function set a value to a default if no value is provided
    if [ "$2" == "" ]; then
        echo $1
    else
        echo $2
    fi
}

list_agents () {
    # Helper function -- list the agents with links -- used in the header function
    count=0
    for agent in "${ta_shortnames[@]}"; do
        echo "- [${ta_names[$count]}](${ta_urls[$count]}) ($agent)"
        count=$(expr ${count} + 1)
    done
}

aries_interop_header () {
    # The summary page header -- markdown format

    cat << EOF

This web site shows the current status of Aries Interoperability between Aries frameworks and agents. While
not yet included in these results, we have a working prototype for testing Aries mobile wallets using the
same tests.

The latest interoperability test results are below. Each row is a test agent, its columns
the results of tests executed in combination with other test agents.
The bolded cell per row shows the results of all tests run for the given test agent. The link on each test
agent name provides more details about results for all test combinations for that test agent. On
that page are links to a full history of the test runs and full details on every executed test. 

The following test agents are currently supported:

$(list_agents)

Want to add your Aries component to this page? You need to add a runset to the
[Aries Agent Test Harness](https://github.com/hyperledger/aries-agent-test-harness).

## Latest Interoperability Results

EOF
}

aries_interop_footer () {
    # The summary page footer -- markdown format

    cat << EOF

- The **bolded results** show all tests involving the "Test Agent", including tests involving only that Test Agent.
- Wondering what the results mean? Please read the brief [introduction to Aries interoperability](aries-interop-intro.md) for some background.
- Select the "Test Agent" links to drill down into the tests being run.

EOF
}

aries_interop_summary_table_header () {
    # The header for the table on the summary page -- static columns, plus one per test agent
    printf "| Test Agent | Scope | Exceptions "
    for agent in "${ta_shortnames[@]}"; do
        printf "| $agent "
    done
    printf "|\\n"

    printf "| ----- | ----- | ----- "
    for agent in "${ta_shortnames[@]}"; do
        printf "| :----: "
    done
    printf "|\\n"
}

sum_print_tests () {
    # Inserts the value of a cell by summing the number of tests involving the two agents
    # passed in as args 1 and 2. Doesn't include skipped runsets. Prints the result at the end.
    # Special handling of arg values are the same -- puts markdown bold around the results.
    passed=0
    total=0
    file_num=0
    for file in ${workflows}; do
        agents=${ACME[$file_num]}${BOB[$file_num]}${FABER[$file_num]}${MALLORY[$file_num]}
        if [[ $agents =~ $1 && $agents =~ $2 && "${SKIP[$file_num]}" == "" ]]; then
            passed=$(expr $passed + ${PASSED[$file_num]} ) 
            total=$(expr $total + ${TOTAL_CASES[$file_num]} )
        fi
        file_num=$(expr ${file_num} + 1 )
    done
    if [ ${total} -eq 0 ]; then
        percent=0
    else
        percent=$((${passed}*100/${total}))
    fi
    bold=""
    if [ "$1" == "$2" ]; then
        bold="**"
    fi
    printf "| ${bold}%d / %d<br>%d%%${bold} " ${passed} ${total} ${percent}
}

aries_interop_summary_table () {
    # Prints the data rows of the summary page table -- iterating over the list of agents
    # Calls the "sum_print_tests" function to sum across runsets for a test agent.
    count=0
    for agent in "${ta_tlas[@]}"; do
        printf "| [${ta_shortnames[$count]}](${agent}.md)"
        printf "| ${ta_scopes[$count]} "
        printf "| ${ta_exceptions[$count]} "
        count=$(expr $count + 1)
        for other_agent in "${ta_tlas[@]}"; do
            sum_print_tests $agent $other_agent
        done
        printf "|\\n"
    done
}

# Inline code starts here
# Collect all the data about each runset into a series of arrays - one per data element
count=0
for file in ${workflows}; do
    RUNSET[$count]=$(echo $file | sed "s/.*ness-//" | sed "s/.yml//")
    # set -x
    RUNSET_NAME[$count]=$( default_value ${RUNSET[$count]} "$(grep RUNSET_NAME $file |  sed 's/^.*: //' | sed 's/["]//g')" )
    SCOPE[$count]=$(grep "# Scope" $file |  sed 's/^.*: //' | sed 's/["]//g')
    EXCEPTIONS[$count]=$(grep "# Exceptions" $file |  sed 's/^.*: //' | sed 's/["]//g')
    # Optional -- to skip a runset from inclusion in the results.
    SKIP[$count]=$(grep "# SKIP" $file )
    RUNSET_LINK[$count]=${RUNSET}
    SUMMARY[$count]=$(grep "^#" $file | sed 's/^#[ ]*//'  | sed '/Current/,$d' | sed '1,/Summary/d' | sed 's/$/\\n/' | sed 's/^ //')
    CURRENT_STATUS[$count]=$(grep "^#" $file | sed 's/^#[ ]*//'  | sed '/^End/,$d' | sed -n '/Current/,$p' | sed '1d' | sed 's/^ //')
    ALLURE_PROJECT[$count]=$(grep "REPORT_PROJECT" $file | sed -n '1p' | sed 's/.*: //' | sed 's/ *$//' )
    ALLURE_LINK[$count]="https://allure.vonx.io/allure-docker-service-ui/projects/${ALLURE_PROJECT[$count]}/reports/latest"
    ALLURE_BEHAVIORS_LINK[$count]="https://allure.vonx.io/api/allure-docker-service/projects/${ALLURE_PROJECT[$count]}/reports/latest/index.html?redirect=false#behaviors"
    ALLURE_SUMMARY[$count]=$(curl --silent https://allure.vonx.io/api/allure-docker-service/projects/${ALLURE_PROJECT[$count]}/reports/latest/widgets/summary.json)
    ALLURE_ENVIRONMENT[$count]=$(curl --silent https://allure.vonx.io/api/allure-docker-service/projects/${ALLURE_PROJECT[$count]}/reports/latest/widgets/environment.json)
    ACME[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/acme.agent.*/acme.agent/' | sed 's/-agent-backchannel.*//' | sed 's/.*\[ "//' )
    BOB[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*acme.agent/acme.agent/' | sed 's/bob.agent.*/bob.agent/' |sed 's/-agent-backchannel.*//' | sed 's/.*\[ "//' )
    FABER[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*bob.agent/bob.agent/' | sed 's/faber.agent.*/faber.agent/' |sed 's/-agent-backchannel.*//' | sed 's/.*\[ "//' )
    MALLORY[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*faber.agent/faber.agent/' | sed 's/mallory.agent.*/mallory.agent/' |sed 's/-agent-backchannel.*//' | sed 's/.*\[ "//' )
    ACME_VERSION[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*role.acme//' | sed 's/acme.agent.*//' | sed 's/.* \[ "//' | sed 's/".*//' )
    BOB_VERSION[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*role.bob//' | sed 's/bob.agent.*//' | sed 's/.* \[ "//' | sed 's/".*//' )
    FABER_VERSION[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*role.faber//' | sed 's/faber.agent.*//' | sed 's/.* \[ "//' | sed 's/".*//' )
    MALLORY_VERSION[$count]=$(echo ${ALLURE_ENVIRONMENT[$count]} | sed 's/.*role.mallory//' | sed 's/mallory.agent.*//' | sed 's/.* \[ "//' | sed 's/".*//' )
    TOTAL_CASES[$count]=$( echo ${ALLURE_SUMMARY[$count]} | sed  's/.*"total" : \([0-9]*\).*/\1/' )
    PASSED[$count]=$( echo ${ALLURE_SUMMARY[$count]} | sed  's/.*"passed" : \([0-9]*\).*/\1/' )
    FAILED[$count]=$( echo ${ALLURE_SUMMARY[$count]} | sed  's/.*"failed" : \([0-9]*\).*/\1/' )
    if [ ${TOTAL_CASES[$count]} -eq 0 ]; then
        PERCENT[$count]=0
    else
        PERCENT[$count]=$((PASSED[$count]*100/TOTAL_CASES[$count]))
    fi
    epoch_seconds=$(echo ${ALLURE_SUMMARY[$count]} | sed 's/.*"stop" : \([0-9]\{10\}\).*/\1/' )
    if [ ${machine} == 'Mac' ]; then
        ALLURE_DATE[$count]=$( date -j -f %s ${epoch_seconds} )
    else
        ALLURE_DATE[$count]=$( date -d@${epoch_seconds} )
    fi

    count=$(expr ${count} + 1)
done

# echo ACME: ${ACME_VERSION[@]}
# echo BOB: ${BOB_VERSION[@]}
# echo FABER: ${FABER_VERSION[@]}
# echo MALLORY: ${MALLORY_VERSION[@]}

# First write the summary file -- make sure to replace the old version with a ">" and ">>" for the rest
outfile=docs/README.md
# Remove the file if it exists
rm -f $outfile

# Title of the page
echo -e '# Aries Interoperability Information\n' >>$outfile

# Header part of the page
aries_interop_header >>$outfile

# Summary table header
aries_interop_summary_table_header >>$outfile

# Summary table data
aries_interop_summary_table >>$outfile

# Finished with the table -- add in the footer and done with the summary file
aries_interop_footer >>$outfile
echo -e "\\n*Results last updated: $(date | sed 's/  / /g')*" >>$outfile
echo "" >>$outfile

# Iterate through the test agents and create a file per test agent.
ta_num=0
for agent in "${ta_tlas[@]}"; do
    outfile=docs/${agent}.md
    # Remove the file if it exists
    rm -f $outfile
    
    # echo -e "---\\nsort: ${ta_num} # follow a certain sequence of letters or numbers\\n---" >>$outfile
    echo -e "# ${ta_names[$ta_num]} Interoperability\\n" >>$outfile
    echo -e "## Runsets with ${ta_shortnames[$ta_num]}\\n" >>$outfile
    
    # Print a table of details
    echo "| Runset | ACME<br>(Issuer) | Bob<br>(Holder) | Faber<br>(Verfier) | Mallory<br>(Holder) | Scope | Results | " >>$outfile
    echo "| ------ | :--------------: | :-------------: | :----------------: | :-----------------: | ----- | :-----: | " >>$outfile
    runset_num=0
    # Iterate through the workflows and find the ones involving this test agent -- ignoring skipped files
    # Insert the data into the table
    for file in ${workflows}; do
        agents=${ACME[$runset_num]}${BOB[$runset_num]}${FABER[$runset_num]}${MALLORY[$runset_num]}
        if [[ $agents =~ $agent && "${SKIP[$runset_num]}" == "" ]]; then
            echo -e "| [${RUNSET[$runset_num]}](#runset-${RUNSET[$runset_num]}) | ${ACME[$runset_num]}<br>${ACME_VERSION[$runset_num]} | ${BOB[$runset_num]}<br>${BOB_VERSION[$runset_num]} | ${FABER[$runset_num]}<br>${FABER_VERSION[$runset_num]} | ${MALLORY[$runset_num]}<br>${MALLORY_VERSION[$runset_num]} | ${SCOPE[$runset_num]} | [**${PASSED[$runset_num]} / ${TOTAL_CASES[$runset_num]}<br>${PERCENT[$runset_num]}%**](${ALLURE_BEHAVIORS_LINK[$runset_num]}) |" >>$outfile
        fi
        runset_num=$( expr ${runset_num} + 1)
    done

    # Iterate again through the workflows to write out a section per workflow
    echo -e "\\n## Runset Notes" >>$outfile
    runset_num=0
    for file in ${workflows}; do
        agents=${ACME[$runset_num]}${BOB[$runset_num]}${FABER[$runset_num]}${MALLORY[$runset_num]}
        if [[ $agents =~ $agent && "${SKIP[$runset_num]}" == "" ]]; then
            echo -e "\\n### Runset **${RUNSET[$runset_num]}**\\n" >>$outfile
            echo -e "Runset Name: ${RUNSET_NAME[$runset_num]}" >>$outfile
            echo -e "\\n\`\`\`tip\\n**Latest results: ${PASSED[$runset_num]} out of ${TOTAL_CASES[$runset_num]} (${PERCENT[$runset_num]}%)**\\n" >>$outfile
            echo -e "\\n*Last run: ${ALLURE_DATE[$runset_num]}*\\n\`\`\`\\n" >>$outfile
            echo -e "#### Current Runset Status" >>$outfile
            # Print the status text from the workflow file -- or a default message
            if [ "${CURRENT_STATUS[$runset_num]}" == "" ]; then
                echo -e "\`\`\`warning\\nNo test status note is available for this runset. Please update: $file.\\n\`\`\`\\n" >>$outfile
            else
                echo -e "${CURRENT_STATUS[$runset_num]}\\n" >>$outfile
            fi
            # Links to the allure results
            echo -e "#### Runset Details\\n" >>$outfile
            echo -e "- Results grouped by [executed Aries RFCs executed](${ALLURE_BEHAVIORS_LINK[$runset_num]})" >>$outfile
            echo -e "- Results by [history](${ALLURE_LINK[$runset_num]})\\n" >>$outfile
        fi
        runset_num=$( expr ${runset_num} + 1)
    done
    # Link to the summary page
    echo "Jump back to the [interoperability summary](./README.md)." >>$outfile
    # And we're done for this file
    echo "" >>$outfile
    ta_num=$( expr ${ta_num} + 1)
done
