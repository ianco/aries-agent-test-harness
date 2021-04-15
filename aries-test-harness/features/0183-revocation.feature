@revocation @AIP20
Feature: RFC 0183 Aries agent credential revocation and revocation notification

   Background: create a schema and credential definition in order to issue a credential
      Given "Acme" has a public did
      And "Acme" is ready to issue a credential

   @T001-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential revoked by Issuer and Holder attempts to prove with a prover that doesn't care if it was revoked
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And "Faber" sends a <request_for_proof> presentation to "Bob"
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T001.1-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @Indy @DIDExchangeConnection
   Scenario Outline: Credential revoked by Issuer and Holder attempts to prove with a prover that doesn't care if it was revoked with a DID Exchange connection
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And "Faber" sends a <request_for_proof> presentation to "Bob"
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T001.2-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @MobileTest
   Scenario Outline: Credential revoked by Issuer and Holder attempts to prove with a prover that doesn't care if it was revoked
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And "Faber" sends a <request_for_proof> presentation to "Bob"
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T002-HIPE0011 @critical @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential revoked and replaced with a new updated credential, holder proves claims with the updated credential with timesstamp
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And <issuer> issues a new credential to "Bob" with <new_credential_data>
      And "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | new_credential_data | timeframe | request_for_proof              | presentation                       |
         | Acme   | Data_DL_MinValues | Data_DL_MaxValues   | now:now   | proof_request_DL_revoc_address | presentation_DL_revoc_address_w_ts |

   @T002.1-HIPE0011 @normal @wip @NegativeTest @AcceptanceTest @Schema_Health_Consent_Revoc @Indy
   Scenario Outline: Credential revoked and replaced with a new updated credential, holder proves claims with the updated credential with no timestamp
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And <issuer> issues a new credential to "Bob" with <new_credential_data>
      And "Faber" sends a <request_for_proof> presentation to "Bob"
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data      | new_credential_data          | request_for_proof                         | presentation                             |
         | Acme   | Data_BI_HealthValues | Data_BI_HealthValues_Reissue | proof_request_health_consent_revoc_expiry | presentation_health_consent_revoc_expiry |

   @T003-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Proof in process while Issuer revokes credential before presentation and the verifier doesn't care about revocation status
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When "Faber" sends a <request_for_proof> presentation to "Bob"
      And <issuer> revokes the credential
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T004-HIPE0011 @normal @wip @AcceptanceTest @ExceptionTest @Schema_DriversLicense_Revoc @Indy @delete_cred_from_wallet
   Scenario Outline: Credential revoked and replaced with a new updated credential, get possible credentials from agent wallet
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When <issuer> revokes the credential
      And <issuer> issues a new credential to "Bob" with <new_credential_data>
      And "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | new_credential_data | timeframe | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MinValues | Data_DL_MaxValues   | now:now   | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T005-HIPE0011 @normal @AcceptanceTest @ExceptionTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential is revoked inside the non-revocation interval
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential within <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data   | timeframe       | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MinValues | -86400:+86400   | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | -604800:now     | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | -604800:+604800 | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T006-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential is revoked before the non-revocation instant
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential before <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity before <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data   | timeframe       | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MinValues | now:now         | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MaxValues | +86400:+86400   | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | +604800:+604800 | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | -1:-1           | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T006.1-HIPE0011 @normal @AcceptanceTest @ExceptionTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential is revoked before the non-revocation interval
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential before <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity before <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data   | timeframe  | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | 0:+86400   | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | -1:+604800 | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T006.2-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @MobileTest
   Scenario Outline: Credential is revoked before the non-revocation instant
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential before <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity before <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data   | timeframe       | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MinValues | now:now         | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MaxValues | +86400:+86400   | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | +604800:+604800 | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | -1:-1           | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T007-HIPE0011 @normal @wip @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential is revoked after the non-revocation instant
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential after <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity after <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | timeframe       | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | -86400:-86400   | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MaxValues | -604800:-604800 | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T008-HIPE0011 @normal @wip @DerivedTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Credential is revoked during a timeframe with an open ended FROM or TO date
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      And <issuer> has revoked the credential within <timeframe>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof with the revoked credential
      And "Faber" acknowledges the proof
      Then "Bob" has the proof unverified

      Examples:
         | issuer | credential_data   | timeframe | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MinValues | :now      | proof_request_DL_revoc_address | presentation_DL_revoc_address |
         | Acme   | Data_DL_MinValues | now:      | proof_request_DL_revoc_address | presentation_DL_revoc_address |


   @T009-HIPE0011 @wip @DerivedTest @NegativeTest @Schema_DriversLicense_Revoc @NeedsReview
   Scenario Outline: Revoke attempt be done by the holder or a verifier
      Given "3" agents
         | name  | role     |
         | Acme  | issuer   |
         | Bob   | holder   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from "Acme" with <credential_data>
      When <role> revokes the credential
      Then <role> will get an error stating ...
      And "Bob" can make a proof with the credential

      Examples:
         | issuer | credential_data   | role     | request_for_proof        | presentation            |
         | Acme   | Data_DL_MaxValues | holder   | proof_request_DL_address | presentation_DL_address |
         | Acme   | Data_DL_MaxValues | verifier | proof_request_DL_address | presentation_DL_address |


   @T010-HIPE0011 @wip @DerivedTest @NegativeTest @Schema_DriversLicense @NeedsReview
   Scenario Outline: Attempt to revoke an unrevokable credential.
      Given "3" agents
         | name  | role     |
         | Acme  | issuer   |
         | Bob   | holder   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from "Acme" with <credential_data>
      When "Acme" revokes the credential
      Then "Acme" receives an error stating …
      And "Bob" can make a proof with the credential

      Examples:
         | issuer | credential_data   | request_for_proof        | presentation            |
         | Acme   | Data_DL_MinValues | proof_request_DL_address | presentation_DL_address |


   @T011-HIPE0011 @wip @AcceptanceTest @Schema_DriversLicense_Revoc @NeedsReview
   Scenario Outline: Issuer revokes multiple credentials in the same transaction
      Given "3" agents
         | name  | role     |
         | Acme  | issuer   |
         | Bob   | holder   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from "Acme" with <credential_data>
      And "Faber" has an issued credential from "Acme" with <credential_data_2>
      When "Acme" revokes "Bob’s" credential
      And "Acme" revokes "Faber’s" credential
      Then "Bob" cannot make a proof with the credential
      And "Faber" cannot make a proof with the credential

      Examples:
         | issuer | credential_data   | request_for_proof        | presentation            |
         | Acme   | Data_DL_MaxValues | proof_request_DL_address | presentation_DL_address |

   @T012-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc
   Scenario Outline: Revocable Credential not revoked and Holder attempts to prove without a non-revocation interval
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When "Faber" sends a <request_for_proof> presentation to "Bob"
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | request_for_proof              | presentation                  |
         | Acme   | Data_DL_MaxValues | proof_request_DL_revoc_address | presentation_DL_revoc_address |

   @T013-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense @Indy @MobileTest
   Scenario Outline: Non-revocable Credential, not revoked, and holder proves claims with the credential with timesstamp
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | timeframe | request_for_proof        | presentation                 |
         | Acme   | Data_DL_MinValues | now:now   | proof_request_DL_address | presentation_DL_address_w_ts |

   @T014-HIPE0011 @normal @AcceptanceTest @Schema_DriversLicense_Revoc @Indy
   Scenario Outline: Revocable Credential, not revoked, and holder proves claims with the credential with timesstamp
      Given "2" agents
         | name  | role     |
         | Bob   | prover   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from <issuer> with <credential_data>
      When "Faber" sends a <request_for_proof> presentation to "Bob" with credential validity during <timeframe>
      And "Bob" makes the <presentation> of the proof
      And "Faber" acknowledges the proof
      Then "Bob" has the proof verified

      Examples:
         | issuer | credential_data   | timeframe | request_for_proof              | presentation                       |
         | Acme   | Data_DL_MinValues | now:now   | proof_request_DL_revoc_address | presentation_DL_revoc_address_w_ts |


   @T001-RFC0183 @RFC0183 @wip @AcceptanceTest @Schema_DriversLicense_Revoc @NeedsReview
   Scenario Outline: Issuer revokes a credential and then sends notification
      Given "3" agents
         | name  | role     |
         | Acme  | issuer   |
         | Bob   | holder   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from "Acme" with <credential_data>
      When "Acme" revokes the credential
      And "Acme" sends a revocation notification
      Then "Bob" receives the revocation notification
      And "Bob" cannot make a proof with the credential

      Examples:
         | issuer | credential_data   | request_for_proof        | presentation            |
         | Acme   | Data_DL_MaxValues | proof_request_DL_address | presentation_DL_address |


   @T002-RFC0183 @RFC0183 @wip @AcceptanceTest @Schema_DriversLicense_Revoc @NeedsReview
   Scenario Outline: Issuer revokes multiple credentials for multiple holders and sends notification
      Given "3" agents
         | name  | role     |
         | Acme  | issuer   |
         | Bob   | holder   |
         | Faber | verifier |
      And "Faber" and "Bob" have an existing connection
      And "Bob" has an issued credential from "Acme" with <credential_data>
      And “Faber” has an issued credential from "Acme" with <credential_data_2>
      When "Acme" revokes "Bob’s" credential
      And "Acme" sends a revocation notification to "Bob"
      And "Acme" revokes "Faber’s" credential
      And "Acme" sends a revocation notification to "Faber"
      Then "Bob" receives the revocation notification
      And "Faber" receives the revocation notification
      And "Bob" cannot make a proof with the credential
      And "Faber" cannot make a proof with the credential

      Examples:
         | issuer | credential_data   | request_for_proof        | presentation            |
         | Acme   | Data_DL_MaxValues | proof_request_DL_address | presentation_DL_address |
