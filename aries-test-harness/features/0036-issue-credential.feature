 @RFC0036
Feature: RFC 0036 Aries agent issue credential

  Background: create a schema and credential definition in order to issue a credential
    Given "Acme" has a public did
    And "Acme" is ready to issue a credential

  @T001-RFC0036 @AIP10 @critical @AcceptanceTest @Indy
  Scenario: Issue a credential with the Holder beginning with a proposal
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Bob" proposes a credential to "Acme"
    And "Acme" offers a credential
    And "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T001.1-RFC0036 @AIP10 @critical @AcceptanceTest @Indy @DIDExchangeConnection
  Scenario: Issue a credential with the Holder beginning with a proposal with DID Exchange Connection
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Bob" proposes a credential to "Acme"
    And "Acme" offers a credential
    And "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T002-RFC0036 @AIP10 @normal @AcceptanceTest @Indy
  Scenario: Issue a credential with the Holder beginning with a proposal with negotiation
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    And "Bob" proposes a credential to "Acme"
    And "Acme" offers a credential
    When "Bob" negotiates the offer with another proposal of the credential to "Acme"
    And "Acme" Offers the credential
    And "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T003-RFC0036 @AIP10 @critical @AcceptanceTest @Indy
  Scenario: Issue a credential with the Issuer beginning with an offer
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Acme" offers a credential
    And "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T003.1-RFC0036 @PerformanceTest @Indy
  Scenario: Issue many credentials with the Issuer beginning with an offer
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Acme" sends "300" credentials in batches of "32"
    Then "Bob" receives "300" credentials

  @T004-RFC0036 @AIP10 @normal @AcceptanceTest @Indy
  Scenario: Issue a credential with the Issuer beginning with an offer with negotiation
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    And "Acme" offers a credential
    When "Bob" negotiates the offer with a proposal of the credential to "Acme"
    And "Acme" Offers the credential
    And "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T005-RFC0036 @AIP10 @minor @wip @AcceptanceTest
  Scenario: Issue a credential with negotiation beginning from a credential request
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Bob" requests the credential
    And "Acme" offers a credential
    When "Bob" negotiates the offer with a proposal of the credential to "Acme"
    And "Acme" offers a credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued

  @T006-RFC0036 @AIP10 @critical @wip @AcceptanceTest
  Scenario: Issue a credential with the Holder beginning with a request and is accepted
    Given "2" agents
      | name | role   |
      | Acme | issuer |
      | Bob  | holder |
    And "Acme" and "Bob" have an existing connection
    When "Bob" requests the credential
    And "Acme" issues the credential
    And "Bob" acknowledges the credential issue
    Then "Bob" has the credential issued