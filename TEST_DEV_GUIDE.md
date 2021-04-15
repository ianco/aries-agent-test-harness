# Test Development Guidelines<!-- omit in toc -->

## Contents<!-- omit in toc -->

- [Writing Tests in Gherkin](#writing-tests-in-gherkin)
- [Using Tags](#using-tags)
  - [Defining Protocol Suite Specific Tags](#defining-protocol-suite-specific-tags)
- [Defining Backchannel Operations](#defining-backchannel-operations)
- [Implementing Test Steps](#implementing-test-steps)
  - [Github Actions and Comparing Test Results Day-To-Day](#github-actions-and-comparing-test-results-day-to-day)
- [Implementing the Backchannel](#implementing-the-backchannel)
- [Diving Deeper](#diving-deeper)

## Writing Tests in Gherkin

The Aries Agent Test Harness utilizes a behavioural driven approach to testing. The Python toolset [Behave](https://behave.readthedocs.io/en/stable/index.html) is used to actualize this approach. [Gherkin] is the language syntax used to define test preconditions and context, actions and events, and expected results and outcomes.

The first step in developing a suite of tests for an Aries RFC is to write plain english Gherkin definitions, before any code is written. The only input to the test cases should be the RFC. The test cases should not be driven by agent or agent framework implementations.

The priority is to do "happy path" type tests first, leaving the exception & negative testing until there are multiple suites across protocols of happy path acceptance tests. Write one main scenario then get peers and others familiar with the RFC to review the test. This is important because the structure and language of this initial test may guide the rest of the tests in the suite.

Initial writing of the Gherkin tests themselves are done in a [.feature file](https://behave.readthedocs.io/en/stable/tutorial.html?highlight=feature%20file#features) or in a [GitHub issue](https://github.com/bcgov/aries-agent-test-harness/issues) detailing the test development work to be accomplished. If no GitHub issue exists for the test development work, create one.

To keep test definitions immune to code changes or nomenclatures in code, it is best to express the RFC in high level terms from the user level based on predefined persona, currently `Acme`, `Bob` and `Mallory`, that can be interpreted at the business level without revealing implementation details. For example, `When Acme requests a connection with Bob` instead of `When Acme sends a connection-request to Bob`.  Sometimes this may be cumbersome, so just make it as high level as makes sense.  A full example from the connection protocol might look something like this;

```gherkin
Scenario Outline: establish a connection between two agents
Given we have "2" agents
| name | role |
| Acme | inviter |
| Bob | invitee |
When "Acme" generates a connection invitation
And "Bob" receives the connection invitation
And "Bob" sends a connection request to "Acme"
And "Acme" receives the connection request
And "Acme" sends a connection response to "Bob"
And "Bob" receives the connection response
And "Bob" sends <message> to "Acme"
Then "Acme" and "Bob" have a connection

Examples:
| message |
| trustping |
| ack |
```

Utilize [data tables](https://www.baeldung.com/cucumber-data-tables) and [examples](https://behave.readthedocs.io/en/stable/gherkin.html#scenario-outlines) in the Gherkin definition where possible.

The test cases should use the test persona as follows:

- `Acme`: an enterprise agent with issuer and verifier capabilities
- `Bob`: a holder/prover person
- `Faber` another enterprise agent with issuer and verifier capabilities
- `Mallory`: a malicious holder/prover person

As necessary, other persona will be added. We expect adding `Carol` (another holder/prover person) and perhaps `Thing` (an IOT thing, likely an issuer and verifier). Note that each additional persona requires updates to the running of tests (via the `./manage` script) and introduce operational overhead, so thought should be given before introducing new characters into the test suite.

## Using Tags

The test harness run script supports the use of [tags](https://behave.readthedocs.io/en/latest/tutorial.html?highlight=tags#controlling-things-with-tags) in the feature files to be able to narrow down a test set to be executed. The general tags currently utilized are as follows:

- @AcceptanceTest - Tests based on requirements specifically stated in the RFC. These are tests that will run to verify confirmance of the implemented protocol in the Agents.
- @DerivedFunctionalTest - Tests derived on requirements but not specifically stated in the RFC.
- @P1 - Test Priority
- @P2 - Test Priority
- @P3 - Test Priority
- @P4 - Test Priority
- @NegativeTest - Test that attempts to break the software. ie. change workflow order, use invalid data, etc.
- @ExceptionTest - Tests that are based on requirements that suggest exception cases.
- @NegativeTest - Tests specifically designed to try and break the software
- @SmokeTest - Tests that can be used as a builds smoke or sanity tests.
- @NeedsReview - Tests that have not been reviewed or approved.
- @ReviewedApproved - obvious
- @wip - Tests that are a work in progress and incomplete
- @Done - Finished tests that are expected to Pass if executed against an Agent.
- @AIP10 - Aries Interop Profile version the tests are written for
- @T01-AIP10-RFC0160 - Test Unique Identifier - Please use T for the test cases number, the API version number the test is written for, and the RFC number for the Protocol under test. 
- @WillFail - Tests completed but because of an outstanding bug, they are expected to fail. The test harness looks for this to report on the next tag  
- @OutstandingBug..###..url - When using @WillFail, this tag much also be used. It is comprised of 3 components, OutstandingBug, the bug number, and the bug url. These must be separated by double periods.

### Defining Protocol Suite Specific Tags

There will be cases where there will be a need for Protocol specific tags. This will usually reveal itself when there are optional implementations or where implementations can diverge into 2 or more options. Tests will need to be tagged with the least common option, where no tag means the other option. For example in the connection protocol there are specific tests that exercise the behaviour of the protocol using a Multi Use Invite and a Single Use Invite. The tag @MultiUseInvite is used to differentiate the two, and by default it is expected that MultiUseInvite is the least common option.

Currently Existing Connection Protocol Tags

- @MultiUseInvite - Test utilizes a multi-use invite. Not using this tag and the test expects the invite to be single use.
- @SingleTryOnException
- @RetryableOnException

Defining specific tags should be discussed with the Aries Protocol test community.

## Defining Backchannel Operations

Defining test steps require using and extending the commands and operations to be implemented by the backchannels. The commands and operations are documented in a Google Sheet, located [here](https://bit.ly/AriesTestHarnessScenarios). All operations are also documented in an OpenAPI Spec located [here](./docs/assets/openapi-spec.yml). The OpenAPI spec can be viewed on the Aries Interop page [here](http://aries-interop.info/api). As test developers add new steps to test cases, document the new operations on which they depend in the spreadsheet and the OpenAPI spec. The data from the Google Sheet is available to the backchannels and are used by some to implement the backchannel capabilities. Making the data available is currently a manual process that is done using the following process:

- prepare a branch in your fork of the repo that will be a PR
  - [optional] export the Google Sheet, saving it into this file in the repo: [steps/Mapping Aries Protocols for Testing - Aries Agent Test Scripts.csv](./aries-test-harness/features/Mapping%20Aries%20Protocols%20for%20Testing%20-%20Aries%20Agent%20Test%20Scripts.csv)
- run the command in the `aries-test-harness/features` folder:
  - If you used the public Google sheet, you can skip the previous [optional] step and run: `python genBCData.py`. This wil download the latest version automatically
  - Otherwise run: `python genBCData.py Mapping\ Aries\ Protocols\ for\ Testing\ -\ Aries\ Agent\ Test\ Scripts.csv` to replace the current data file in the `aries-backchannels/data` folder
- submit a PR to update the file

> To Do: This should be changed to a github action that is run on each commit to the repo

## Implementing Test Steps

Follow standard best practices for implementing test steps in Behave, writing the test steps as if the feature is fully supported and then adding code at all levels to support the new test. The process is something like this:

- Study the RFC and define the tests needed to cover at least the happy path requirements of the RFC
  - Raise as issues in the [Aries RFCs](https://github.com/hyperledger/aries-rfcs) repo any deficiencies in the RFC
- Define Gherkin tests using the existing persona
  - Add new persona only if really, really needed
- Execute the new tests, grabbing the skeleton code for the new, unimplemented steps from the behave output, and adding them to the `steps` Python code
- Implement the steps code, defining as needed commands and operations to be added to the backchannel interface
- Update the Google Sheet and OpenAPI spec to add the new commands and operations and regenerate the backchannel operations data file (see [subsection](#defining-backchannel-operations) above)
- If you are also responsible for implementing one or more backchannels, extend the backchannel(s) to support the new commands and operations
- Notify the community of backchannel maintainers of the new tests, commands and operations

Existing backchannels will throw a "NotImplementedException" for any steps that are not implemented in the backchannels, and should include information from the above-mentioned data file.

### Github Actions and Comparing Test Results Day-To-Day

AATH has the capability of checking whether the test results change from day-to-day (in addition to checking that *all* tests have passed).

To enable this checking run AATH as follows:

```bash
PROJECT_ID=acapy ./manage run -d acapy-main -r allure -e comparison -t @AcceptanceTest -t ~@wip
```

In the above, `PROJECT_ID` is the name of the Allure project (`acapy` in the example above), the parameter `-e comparison` is what invokes the comparison (can only be used with the `-r allure` option) and the test scope (the `-t` parameters) must match what is expected for the specified `PROJECT_ID` (as used in the automated GitHub actions).

This comparison is done using a "Known Good Results" ("KGR") file that is checked into GitHub.

When adding a new test, or if a different set of tests is expected to pass or fail, this KGR file must be updated.

The KGR files are checked into [this folder](https://github.com/hyperledger/aries-agent-test-harness/tree/master/aries-test-harness/allure).

To update the file, run the test suite locally (as in the above command) - it will create a "NEW-*" KGR file in [this folder](https://github.com/hyperledger/aries-agent-test-harness/tree/master/aries-test-harness/allure/allure-results) - just copy this file to replace the existing "The-KGR-File-*" for the `PROJECT_ID` under test, and check into GitHub.

## Implementing the Backchannel

See the [README](../aries-agent-test-harness/aries-backchannels/README.md) in the [aries-backchannels](../aries-agent-test-harness/aries-backchannels) folder for details on writing backchannels.

## Diving Deeper
- [Accessing Connection ID in Test Code](ACCESS-CONNECTION-IDS.md)
- [Configuring Tests with Credential Types and Proofs](CONFIGURE-CRED-TYPES.md)
- [Debugging a Backchannel Running Inside a Docker Contaiener](DEBUGGING.md)