---
sort: 1 # follow a certain sequence of letters or numbers
---
# Introduction to Aries Interoperability

This website reports on the interoperability between different Hyperledger Aries agents. Interoperability includes how seamlessly the agents work together, and how well each agent adheres to community-agreed standards such as Aries Interop Profile (AIP) 1.0 and AIP 2.0.

## Why is interoperability important?

As Digital Trust ecosystems evolve they will naturally require many technologies to coexist and cooperate. Worldwide projects will get larger and will start to overlap. Also, stakeholders and users will not care about incompatibilities; they will simply wish to take advantage of Digital Trust benefits. Finally, interoperability ultimately means more than just Aries agents working with each other, as it covers worldwide standards and paves the way for broader compatibility.

For all these reasons interoperability is incredibly important if Hyperledger Aries is to continue to flourish.

## What are Hyperledger Aries agents and frameworks?

Aries agents are the pieces of software that provide Digital Trust services such as issuing and receiving verifiable credentials and verifying presentations of verifiable credentials. Many Aries agents are built on Aries Frameworks, common components that make it easier to create agents -- developers need only add the business logic on top of a framework to make their agent. Agents can be written in different programming languages, and designed for different devices or for use in the cloud.

What unites Aries agents are the standards and protocols they aim to adhere to, and the underlying technologies (cryptography, DIDs and DID utility ledgers and verifiable credentials).

The Aries frameworks and agents currently tested for interoperability with AATH are:

*   [Aries Cloud Agent Python (ACA-Py)](https://github.com/hyperledger/aries-cloudagent-python)
*   [Aries Framework .NET](https://github.com/hyperledger/aries-framework-dotnet)
*   [Aries Framework Go](https://github.com/hyperledger/aries-framework-go)
*   [Aries Framework JavaScript](https://github.com/hyperledger/aries-framework-javascript)

## How is interoperability assessed?

### The Aries Agent Test Harness

Aries Agent Test Harness (AATH) is open-source software that runs a series of Aries interoperability tests and delivers the test results data to this website.

AATH uses a [Behaviour Driven-Development](URL) (BDD) framework to run tests that are designed to exercise the community-designed Aries Protocols, as defined in the [Aries RFC]([https://github.com/hyperledger/aries-rfcs](https://github.com/hyperledger/aries-rfcs)) GitHub repo.

The tests are executed by starting up four Test Agents (“Acme” is an issuer, “Bob” a holder/prover, “Faber” a verifier and Mallory, a sometimes malicious holder/prover), and having the test harness send instructions to the Test Agents to execute the steps of the BDD tests. Each Test Agent is a container that contains the “component under test” (an Aries agent or framework), along with a web server that communicates (using HTTP) with the test harness to receive instructions and report status, and translates and passes on those instructions to the “component under test” using whatever method works for that component. This is pictured in the diagram below, and is covered in more detail in the [AATH Architecture](https://github.com/hyperledger/aries-agent-test-harness#architecture) section of the repo’s README.

![AATH Architecture](assets/aath-arch/aath-arch.png)

### Runsets

A runset is a named set of tests (e.g. “all AIP 1.0 tests”) and test agents (e.g. “ACA-Py and Aries Framework JavaScript”) that are run on a periodic basis — for example, every day. The results of each run of a runset are recorded to a test results repository for analysis and summarized on this site. In general, the order of the Test Agent names indicate the roles played, with the first playing all roles except Bob, the holder/prover). However, exact details of what Test Agents play what roles can be found in the runset details page listed in the left menu and from the summary table.

The set of tests run (the scope) per runset vary by the combined state of the agents involved in a test. For example:

*   Some agents implement Aries Interop Profile (AIP) 1.0, others 2.0 and others, both.
*   Some agents have implemented more features than others, and therefore support more tests,
*   Some agents are unable to support particular tests because of practical limitations of the device they run on (e.g. mobile) or the ease with which that test can be conducted.

For these reasons it’s not possible to say that, for example, an 80% pass result is “good” or 50% is “bad”. The numbers need to be understood in context.

The scope and exceptions columns in the summary and the summary statement found on each runset’s page on this website, document the scope and expectations of runset.

Each runset’s page also provides narrative on the current status of the runset — for example, why some tests of a runset are failing, what issues have been opened and where to address the issue.

### Failing Tests

Tests can fail for many reasons, and much of the work of maintaining the tests and runsets is staying on top of the failures.  The following are some notes about failing tests and what to do about them:

*   Most failures happen when new runsets are added. For example, a new Test Agent is added to the repository and it doesn’t play well with the existing Test Agents.
*   Since most runsets pull the latest main branch code for each Test Agent for each run of the set, errors may be introduced as a result of code added to a Test Agent. Thus, the AATH is an example of a new form of “CI”, Continuous _Interoperability_.
*   With each failure, an evaluation is needed about the cause of the error:
    *   Is the test that is incorrectly interpreting the RFC?
    *   Is the RFC itself wrong?
    *   Is one of the agents/frameworks involved in the testing implementing the RFC incorrectly?
    *   Is the driver (called the Backchannel) that is controlling the agent/framework have a bug?
*   Each failure should result in a GitHub issue being opened in the appropriate repo and the runset narrative updated to note the failure and the issue. Once solved, the runset narrative should be updated to remove the reference to the issue.

## What is Aries Interop Profile?

Aries Interop Profile (AIP) is a set of concepts and protocols that every Aries agent that wants to be interoperable should implement. Specific Aries agents may implement additional capabilities and protocols, but for interoperability, they must implement those defined in an AIP. 

AIP currently has two versions:

*   [AIP 1.0](https://github.com/hyperledger/aries-rfcs/tree/master/concepts/0302-aries-interop-profile#aries-interop-profile-version-10), finalized in January 2020, defines how Aries agents communicate with each other using a single type of verifiable credential
*   [AIP 2.0](https://github.com/hyperledger/aries-rfcs/pull/579), is expected to be finalized in March 2021, builds on AIP 1.0 including how Aries agents can exchange several types of verifiable credentials, including W3C standard verifiable credentials.

AIP versions go through a rigorous community process of discussion and refinement before being agreed upon. During that process, the RFCs that go into each AIP are debated and the specific version of each included RFC is locked down. AIPs are available for anyone to review (and potentially contribute to) in the [Aries RFC repo](https://github.com/hyperledger/aries-rfcs).

## How can I contribute?

For developers improving an Aries agent or framework, each runset’s page has a link to a detailed report in Allure. This allows the specific tests and results to be explored in detail.

If you are a stakeholder interested in improving the results for an agent, this website (and the Allure links, described above) should have enough material for your teams to take action.

Finally, if you want your Aries agent to be added to this website, or wish to expand the tests covered for your agent, your developers can reference the extensive information in the [Aries Agent Test Harness repo](https://github.com/hyperledger/aries-agent-test-harness) on GitHub.

In addition an API reference for backchannels can be found [here](http://aries-interop.info/api.html)